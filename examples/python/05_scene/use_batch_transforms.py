"""Update several rigid poses in a single call. Press Enter at each step."""

import frameviz as fv


def main():
    viz = fv.open(title="Batch transforms")
    try:
        boxes = [viz.add_box(size=[0.25, 0.25, 0.25], position=[x, 0, 0.125],
                             color="blue") for x in (-0.5, 0, 0.5)]
        input("Press Enter to move all three boxes. ")
        # The last four numbers are the identity quaternion in xyzw order.
        viz.set_object_transforms([
            {"handle": box, "pose": [x, 0.5, 0.125, 0, 0, 0, 1]}
            for x, box in zip((-0.5, 0, 0.5), boxes)
        ])
        input("Press Enter to exit. ")
    finally:
        viz.close()


if __name__ == "__main__":
    main()
