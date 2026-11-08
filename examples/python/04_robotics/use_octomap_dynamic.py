"""
Dynamic Octomap Instancing Demo

Demonstrates the update_instances() API for dynamically updating
large batches of instanced primitives (e.g., Octomap occupancy grids).

Usage:
    python use_octomap_dynamic.py
"""
from __future__ import annotations

import time
import numpy as np

import frameviz as fv


def generate_occupancy_grid(
    grid_size: int = 30,
    cell_size: float = 0.1,
    occupancy_prob: float = 0.08,
    seed: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a random occupancy grid and return (positions, colors)."""
    if seed is not None:
        np.random.seed(seed)
    
    # Generate random occupancy
    occupied = np.random.rand(grid_size, grid_size, grid_size) < occupancy_prob
    indices = np.argwhere(occupied)
    
    if len(indices) == 0:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.float32)
    
    # Convert grid indices to positions
    positions = indices.astype(np.float32) * cell_size
    positions += np.array([0.0, 0.0, cell_size * 0.5], dtype=np.float32)
    
    # Color by height (z): blue -> green -> yellow
    z_vals = indices[:, 2].astype(np.float32)
    z_norm = (z_vals - z_vals.min()) / max(z_vals.max() - z_vals.min(), 1.0)
    colors = np.zeros((len(positions), 3), dtype=np.float32)
    colors[:, 0] = z_norm           # R: increases with height
    colors[:, 1] = 1.0 - 0.5 * z_norm  # G: decreases slightly
    colors[:, 2] = 1.0 - z_norm     # B: decreases with height
    
    return positions, colors


def main() -> None:
    print("=" * 60)
    print("FrameViz Dynamic Octomap Instancing Demo")
    print("=" * 60)
    print("\nThis demo shows how to use update_instances() to dynamically")
    print("update large batches of instanced primitives.\n")

    # Configuration
    GRID_SIZE = 30  # 30^3 = 27000 potential cells
    OCCUPANCY_PROB = 0.08  # ~2000 occupied cells per frame
    CELL_SIZE = 0.1
    UPDATE_INTERVAL = 0.1  # seconds between updates
    NUM_UPDATES = 100

    print(f"[1] Connecting to FrameViz...")
    viz = fv.open(window_mode=2)
    print("    ✓ Connected")

    print(f"\n[2] Creating initial occupancy grid...")
    positions, colors = generate_occupancy_grid(GRID_SIZE, CELL_SIZE, OCCUPANCY_PROB, seed=42)
    print(f"    Initial grid: {len(positions)} occupied cells")

    # Create instanced boxes
    handle = viz.add_instances(
        "box",
        positions=positions,
        colors=colors,
        alpha=0.7,
        size=[CELL_SIZE, CELL_SIZE, CELL_SIZE],
    )
    print(f"    ✓ Created instances with handle: {handle}")

    print(f"\n[3] Starting dynamic updates ({NUM_UPDATES} updates, {UPDATE_INTERVAL}s interval)...")
    
    for i in range(NUM_UPDATES):
        time.sleep(UPDATE_INTERVAL)
        
        # Generate new occupancy with different random state
        new_positions, new_colors = generate_occupancy_grid(
            GRID_SIZE, CELL_SIZE, OCCUPANCY_PROB, seed=i + 100
        )
        
        # Update the instances
        start_time = time.perf_counter()
        viz.update_instances(
            handle,
            positions=new_positions,
            colors=new_colors,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        print(f"    Update {i + 1}/{NUM_UPDATES}: {len(new_positions)} cells, {elapsed_ms:.1f}ms")

    print("\n" + "=" * 60)
    print("Demo complete! Press Enter to exit...")
    print("=" * 60)
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass

    viz.close()
    print("\n✓ Connection closed")


if __name__ == "__main__":
    main()
