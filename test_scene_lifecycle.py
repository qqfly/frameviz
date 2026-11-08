#!/usr/bin/env python3
"""
Test script to verify scene lifecycle management fix.

Tests both closing orders:
1. Owner closes first, then shared views
2. Shared views close first, then owner

Expected behavior: Scene should be destroyed in BOTH cases.
"""

import time
import frameviz as fv


def test_owner_closes_first():
    """Test case 1: Owner closes before shared view (was BUG, now FIXED)"""
    print("=" * 70)
    print("Test 1: Owner closes first (previously BUG)")
    print("=" * 70)

    viz1 = fv.open(title="Owner View", x=100, y=100, width=400, height=300, window_mode=0)
    print(f"✓ Created owner view: scene={viz1.scene_id}, owns_scene={viz1._owns_scene}")

    viz2 = fv.open(title="Shared View", share_scene=viz1.scene_id, x=550, y=100, width=400, height=300, window_mode=0)
    print(f"✓ Created shared view: scene={viz2.scene_id}, owns_scene={viz2._owns_scene}")

    # List scenes before closing
    scenes_before = fv.list_scenes()
    scene_ids_before = [s['scene_id'] for s in scenes_before]
    print(f"\nScenes before closing: {len(scenes_before)} scenes")
    for sid in scenes_before:
        print(f"  - {sid['scene_id']}")

    # Close owner first (this was the bug case)
    print(f"\n[1] Closing owner view (viz1)...")
    viz1.close()
    print(f"  ✓ viz1 closed")

    # Check if scene still exists (it should, because viz2 is still using it)
    scenes_mid = fv.list_scenes()
    scene_ids_mid = [s['scene_id'] for s in scenes_mid]
    print(f"\n[2] Scenes after owner closes: {len(scenes_mid)} scenes")
    for sid in scenes_mid:
        print(f"  - {sid['scene_id']}")

    # Close shared view
    print(f"\n[3] Closing shared view (viz2)...")
    viz2.close()
    print(f"  ✓ viz2 closed")

    # Check if scene was destroyed
    scenes_after = fv.list_scenes()
    scene_ids_after = [s['scene_id'] for s in scenes_after]
    print(f"\n[4] Scenes after shared view closes: {len(scenes_after)} scenes")
    for sid in scenes_after:
        print(f"  - {sid['scene_id']}")

    # Verify
    assert viz1.scene_id in scene_ids_before, "Scene should exist before closing"
    assert viz1.scene_id in scene_ids_mid, "Scene should still exist after owner closes (shared view still using it)"
    assert viz1.scene_id not in scene_ids_after, "Scene should be destroyed after last view closes"
    print("\n✓ PASS: Scene was properly destroyed")


def test_shared_closes_first():
    """Test case 2: Shared views close before owner (should work in both versions)"""
    print("\n" + "=" * 70)
    print("Test 2: Shared view closes first (should always work)")
    print("=" * 70)

    viz1 = fv.open(title="Owner View", x=100, y=450, width=400, height=300, window_mode=0)
    print(f"✓ Created owner view: scene={viz1.scene_id}, owns_scene={viz1._owns_scene}")

    viz2 = fv.open(title="Shared View", share_scene=viz1.scene_id, x=550, y=450, width=400, height=300, window_mode=0)
    print(f"✓ Created shared view: scene={viz2.scene_id}, owns_scene={viz2._owns_scene}")

    # List scenes before closing
    scenes_before = fv.list_scenes()
    scene_ids_before = [s['scene_id'] for s in scenes_before]
    print(f"\nScenes before closing: {len(scenes_before)} scenes")
    for sid in scenes_before:
        print(f"  - {sid['scene_id']}")

    # Close shared view first
    print(f"\n[1] Closing shared view (viz2)...")
    viz2.close()
    print(f"  ✓ viz2 closed")

    # Check if scene still exists (it should, because viz1 is still using it)
    scenes_mid = fv.list_scenes()
    scene_ids_mid = [s['scene_id'] for s in scenes_mid]
    print(f"\n[2] Scenes after shared view closes: {len(scenes_mid)} scenes")
    for sid in scenes_mid:
        print(f"  - {sid['scene_id']}")

    # Close owner
    print(f"\n[3] Closing owner view (viz1)...")
    viz1.close()
    print(f"  ✓ viz1 closed")

    # Check if scene was destroyed
    scenes_after = fv.list_scenes()
    scene_ids_after = [s['scene_id'] for s in scenes_after]
    print(f"\n[4] Scenes after owner closes: {len(scenes_after)} scenes")
    for sid in scenes_after:
        print(f"  - {sid['scene_id']}")

    # Verify
    assert viz1.scene_id in scene_ids_before, "Scene should exist before closing"
    assert viz1.scene_id in scene_ids_mid, "Scene should still exist after shared view closes (owner still using it)"
    assert viz1.scene_id not in scene_ids_after, "Scene should be destroyed after last view closes"
    print("\n✓ PASS: Scene was properly destroyed")


def main():
    print("\n" + "=" * 70)
    print("FrameViz Scene Lifecycle Management Test")
    print("=" * 70)

    try:
        test_owner_closes_first()
        test_shared_closes_first()

        print("\n" + "=" * 70)
        print("✓ All tests passed!")
        print("=" * 70)
        return 0

    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
