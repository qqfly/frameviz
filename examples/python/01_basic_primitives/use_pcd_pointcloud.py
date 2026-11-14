"""
FrameViz example - load a PCD point cloud file.

Supports PCD formats:
- ascii
- binary
- binary_compressed (LZF)
"""
from __future__ import annotations

import argparse
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, List

import numpy as np

import frameviz as fv

_LZF = None
try:
    import lzf as _LZF  # type: ignore
except Exception:
    _LZF = None


@dataclass
class PcdHeader:
    fields: List[str]
    sizes: List[int]
    types: List[str]
    counts: List[int]
    width: int
    height: int
    points: int
    data: str
    data_offset: int

    @property
    def point_step(self) -> int:
        return sum(size * count for size, count in zip(self.sizes, self.counts))


def _dtype_from_pcd(field_type: str, size: int) -> np.dtype:
    key = (field_type.upper(), size)
    mapping = {
        ("F", 4): np.float32,
        ("F", 8): np.float64,
        ("I", 1): np.int8,
        ("I", 2): np.int16,
        ("I", 4): np.int32,
        ("I", 8): np.int64,
        ("U", 1): np.uint8,
        ("U", 2): np.uint16,
        ("U", 4): np.uint32,
        ("U", 8): np.uint64,
    }
    if key not in mapping:
        raise ValueError(f"Unsupported PCD field type/size: {field_type}{size}")
    return np.dtype(mapping[key])


def _parse_header(fp: BinaryIO) -> PcdHeader:
    fields: List[str] = []
    sizes: List[int] = []
    types: List[str] = []
    counts: List[int] = []
    width = height = points = None
    data = None

    while True:
        line = fp.readline()
        if not line:
            raise ValueError("PCD header is incomplete")
        line_str = line.decode("utf-8", "ignore").strip()
        if not line_str or line_str.startswith("#"):
            continue
        parts = line_str.split()
        key = parts[0].upper()
        if key == "FIELDS":
            fields = parts[1:]
        elif key == "SIZE":
            sizes = [int(v) for v in parts[1:]]
        elif key == "TYPE":
            types = parts[1:]
        elif key == "COUNT":
            counts = [int(v) for v in parts[1:]]
        elif key == "WIDTH":
            width = int(parts[1])
        elif key == "HEIGHT":
            height = int(parts[1])
        elif key == "POINTS":
            points = int(parts[1])
        elif key == "DATA":
            data = parts[1].lower()
            break

    if not counts:
        counts = [1] * len(fields)
    if points is None:
        if width is None or height is None:
            raise ValueError("PCD header missing POINTS/WIDTH/HEIGHT")
        points = width * height

    if not (fields and sizes and types):
        raise ValueError("PCD header missing FIELDS/SIZE/TYPE")
    if not (len(fields) == len(sizes) == len(types) == len(counts)):
        raise ValueError("PCD header has inconsistent field metadata")
    if data is None:
        raise ValueError("PCD header missing DATA")

    return PcdHeader(
        fields=fields,
        sizes=sizes,
        types=types,
        counts=counts,
        width=width or 0,
        height=height or 0,
        points=points,
        data=data,
        data_offset=fp.tell(),
    )


def _lzf_decompress_py_variant(data: bytes, expected_size: int, length_first: bool) -> bytes:
    out = bytearray(expected_size)
    ip = 0
    op = 0
    in_len = len(data)
    out_len = expected_size

    while ip < in_len:
        ctrl = data[ip]
        ip += 1

        if ctrl < 32:
            length = ctrl + 1
            if ip + length > in_len or op + length > out_len:
                raise ValueError("LZF literal run out of bounds")
            out[op:op + length] = data[ip:ip + length]
            ip += length
            op += length
            continue

        length = ctrl >> 5
        if length_first and length == 7:
            if ip >= in_len:
                raise ValueError("LZF back reference length truncated")
            length += data[ip]
            ip += 1

        if ip >= in_len:
            raise ValueError("LZF back reference truncated")
        ref = op - ((ctrl & 0x1F) << 8) - 1
        ref -= data[ip]
        ip += 1

        if (not length_first) and length == 7:
            if ip >= in_len:
                raise ValueError("LZF back reference length truncated")
            length += data[ip]
            ip += 1
        length += 2

        if ref < 0 or op + length > out_len:
            raise ValueError("Invalid LZF back reference")

        for _ in range(length):
            out[op] = out[ref]
            op += 1
            ref += 1

    if op != expected_size:
        raise ValueError(f"LZF size mismatch: expected {expected_size}, got {op}")
    return bytes(out)


def _lzf_decompress_py(data: bytes, expected_size: int) -> bytes:
    try:
        return _lzf_decompress_py_variant(data, expected_size, length_first=False)
    except ValueError:
        return _lzf_decompress_py_variant(data, expected_size, length_first=True)


def _lzf_decompress(data: bytes, expected_size: int) -> bytes:
    if _LZF is not None:
        try:
            result = _LZF.decompress(data, expected_size)
            if result is not None:
                return result
        except Exception:
            pass
    return _lzf_decompress_py(data, expected_size)


def _extract_positions_field_major(raw: bytes, header: PcdHeader) -> np.ndarray:
    offsets = []
    offset = 0
    for size, count in zip(header.sizes, header.counts):
        field_bytes = size * count * header.points
        offsets.append((offset, field_bytes))
        offset += field_bytes

    if offset != len(raw):
        raise ValueError("PCD decompressed size does not match header metadata")

    field_map = {}
    view = memoryview(raw)
    for name, (offset, field_bytes), size, field_type, count in zip(
        header.fields,
        offsets,
        header.sizes,
        header.types,
        header.counts,
    ):
        if name not in {"x", "y", "z"}:
            continue
        dtype = _dtype_from_pcd(field_type, size)
        arr = np.frombuffer(view[offset:offset + field_bytes], dtype=dtype, count=header.points * count)
        if count > 1:
            arr = arr.reshape(header.points, count)
        field_map[name] = arr

    if not all(k in field_map for k in ("x", "y", "z")):
        raise ValueError("PCD file missing x/y/z fields")

    positions = np.column_stack([field_map["x"], field_map["y"], field_map["z"]])
    return positions.astype(np.float32, copy=False)


def _extract_positions_interleaved(raw: bytes, header: PcdHeader) -> np.ndarray:
    dtype_fields: List[tuple] = []
    for name, size, field_type, count in zip(
        header.fields,
        header.sizes,
        header.types,
        header.counts,
    ):
        base = _dtype_from_pcd(field_type, size)
        if count == 1:
            dtype_fields.append((name, base))
        else:
            dtype_fields.append((name, base, (count,)))

    dtype = np.dtype(dtype_fields)
    expected = header.points * header.point_step
    if len(raw) < expected:
        raise ValueError("PCD binary data is truncated")

    cloud = np.frombuffer(raw, dtype=dtype, count=header.points)
    if not all(name in cloud.dtype.names for name in ("x", "y", "z")):
        raise ValueError("PCD file missing x/y/z fields")
    positions = np.column_stack([cloud["x"], cloud["y"], cloud["z"]])
    return positions.astype(np.float32, copy=False)


def load_pcd_points(path: Path) -> np.ndarray:
    with path.open("rb") as fp:
        header = _parse_header(fp)

        if header.data == "ascii":
            data = np.loadtxt(fp, dtype=np.float32)
            if data.ndim == 1:
                data = data.reshape(1, -1)
            field_indices = {name: idx for idx, name in enumerate(header.fields)}
            try:
                positions = data[:, [field_indices["x"], field_indices["y"], field_indices["z"]]]
            except KeyError as exc:
                raise ValueError("PCD file missing x/y/z fields") from exc
            return positions.astype(np.float32, copy=False)

        if header.data == "binary":
            raw = fp.read()
            return _extract_positions_interleaved(raw, header)

        if header.data == "binary_compressed":
            if _LZF is None:
                print("Note: python-lzf not found; using pure Python LZF decompressor (slower).")
            header_bytes = fp.read(8)
            if len(header_bytes) != 8:
                raise ValueError("PCD compressed header is incomplete")
            compressed_size, uncompressed_size = struct.unpack("<II", header_bytes)
            compressed = fp.read(compressed_size)
            if len(compressed) != compressed_size:
                raise ValueError("PCD compressed data is truncated")
            raw = _lzf_decompress(compressed, uncompressed_size)
            return _extract_positions_field_major(raw, header)

        raise ValueError(f"Unsupported PCD DATA format: {header.data}")


def height_colors(z: np.ndarray) -> np.ndarray:
    z_min = float(np.min(z))
    z_max = float(np.max(z))
    denom = z_max - z_min if z_max > z_min else 1.0
    t = (z - z_min) / denom
    colors = np.zeros((z.shape[0], 3), dtype=np.float32)
    colors[:, 0] = np.clip(t, 0.0, 1.0)
    colors[:, 2] = 1.0 - colors[:, 0]
    return colors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    default_pcd_dir = repo_root / "data" / "models" / "pointcloud"
    default_file = "synthetic_cloud.pcd"

    parser = argparse.ArgumentParser(description="FrameViz PCD loader example")
    parser.add_argument(
        "--data-dir",
        type=Path,
        help=f"Path to pointcloud data directory (default: {default_pcd_dir})",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=default_file,
        help=f"PCD filename within data-dir (default: {default_file})",
    )
    parser.add_argument("--path", type=Path, help="Direct path to PCD file (overrides --data-dir and --file)")
    parser.add_argument("--stride", type=int, default=1, help="Point stride (>=1)")
    parser.add_argument("--point-size", type=float, default=2.0, help="Point size in pixels")
    parser.add_argument("--no-color", action="store_true", help="Disable height-based coloring")
    parser.add_argument("--center", action="store_true", help="Center cloud at origin")
    args = parser.parse_args()

    # Determine PCD path
    if args.path:
        pcd_path = args.path.expanduser()
    else:
        data_dir = args.data_dir if args.data_dir else default_pcd_dir
        pcd_path = data_dir / args.file
    if not pcd_path.is_file():
        print(f"PCD file not found: {pcd_path}")
        print("Use: python use_pcd_pointcloud.py --path /path/to/file.pcd")
        return 1

    print(f"Loading PCD: {pcd_path}")
    # Use the sample's coordinates as-is. For millimeter input, apply a 0.001 scale.
    points = load_pcd_points(pcd_path)
    total = points.shape[0]
    stride = max(1, args.stride)

    if stride > 1:
        points = points[::stride].copy()
    print(f"Loaded points: {points.shape[0]} (stride={stride}, original={total})")

    if args.center:
        points = points - points.mean(axis=0)

    colors = None if args.no_color else height_colors(points[:, 2])

    viz = fv.open()

    viz.add_points(points, colors=colors, size=args.point_size)
    viz.add_axes(length=0.5)
    viz.set_camera_pose(eye=[2.0, -2.0, 1.5], target=[0, 0, 0])

    print("Render complete. Press Enter to exit...")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass

    viz.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
