"""Shared argument handling for the public rigid scene APIs."""
from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real
from typing import Any

_NODE_FIELDS = {"parent", "name", "tags", "position", "quaternion", "pose", "geometry_scale"}


def components(value: Any, length: int, field: str) -> list[float]:
    try:
        items = list(value)
    except TypeError as exc:
        raise ValueError(f"{field} requires {length} finite numbers") from exc
    if len(items) != length or any(isinstance(item, bool) or not isinstance(item, Real) for item in items):
        raise ValueError(f"{field} requires {length} finite numbers")
    try:
        result = [float(item) for item in items]
    except OverflowError as exc:
        raise ValueError(f"{field} requires {length} finite numbers") from exc
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{field} requires {length} finite numbers")
    return result


def rigid_pose(
    value: Any = None,
    *,
    position: Any = None,
    quaternion: Any = None,
    pos: Any = None,
    quat: Any = None,
) -> dict[str, list[float]]:
    explicit = value is not None or position is not None or quaternion is not None
    if value is not None:
        if any(field is not None for field in (position, quaternion, pos, quat)):
            raise ValueError("pose cannot be combined with separate position or quaternion arguments")
        if isinstance(value, Mapping):
            if set(value) - {"position", "quaternion", "pos", "quat"}:
                raise ValueError("pose accepts translation and rotation fields")
            position, quaternion = value.get("position"), value.get("quaternion")
            pos, quat = value.get("pos"), value.get("quat")
        else:
            items = components(value, 7, "pose")
            position, quaternion = items[:3], items[3:]

    p = components(position, 3, "position") if position is not None else None
    old_p = components(pos, 3, "pos") if pos is not None else None
    q = components(quaternion, 4, "quaternion") if quaternion is not None else None
    old_q = components(quat, 4, "quat") if quat is not None else None
    if p is not None and old_p is not None and p != old_p:
        raise ValueError("conflicting position and pos arguments")
    if q is not None and old_q is not None and q != old_q:
        raise ValueError("conflicting quaternion and quat arguments")
    p = p or old_p or [0.0, 0.0, 0.0]
    q = q or old_q or [0.0, 0.0, 0.0, 1.0]
    maximum = max(map(abs, q))
    if maximum == 0:
        if explicit:
            raise ValueError("quaternion must be nonzero")
        q = [0.0, 0.0, 0.0, 1.0]
    else:
        q = [part / maximum for part in q]
        norm = math.hypot(*q)
        q = [part / norm for part in q]
    return {"position": p, "quaternion": q} if explicit else {"pos": p, "quat": q}


def node_arguments(
    options: Mapping,
    *,
    pos: Any = None,
    quat: Any = None,
    scale: Any = None,
    default_pose: bool = False,
) -> dict[str, Any]:
    unknown = set(options) - _NODE_FIELDS
    if unknown:
        raise TypeError(f"Unexpected scene object options: {', '.join(sorted(unknown))}")
    args = {key: options[key] for key in ("parent", "name", "tags") if options.get(key) is not None}
    if "parent" in args and (not isinstance(args["parent"], str) or not args["parent"]):
        raise ValueError("parent must be an object ID or None")
    if "name" in args and not isinstance(args["name"], str):
        raise ValueError("name must be a string")
    if "tags" in args and not isinstance(args["tags"], dict):
        raise ValueError("tags must be a JSON object")
    pose = options.get("pose")
    position = options.get("position")
    quaternion = options.get("quaternion")
    if default_pose or any(field is not None for field in (pose, position, quaternion, pos, quat)):
        args["pose"] = rigid_pose(pose, position=position, quaternion=quaternion, pos=pos, quat=quat)
    canonical_scale = options.get("geometry_scale")
    old_scale = components(scale, 3, "scale") if scale is not None else None
    if canonical_scale is not None:
        geometry_scale = components(canonical_scale, 3, "geometry_scale")
        if old_scale is not None and old_scale != geometry_scale:
            raise ValueError("conflicting geometry_scale and scale arguments")
        args["geometry_scale"] = geometry_scale
    elif old_scale is not None:
        args["geometry_scale"] = old_scale
    return args
