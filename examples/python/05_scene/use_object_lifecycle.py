"""Clone, hide and delete objects using public handles. Press Enter at each step."""

import frameviz as fv


def main():
    viz = fv.open(title="Object lifecycle")
    try:
        box = viz.add_box(position=[-0.6, 0, 0.3], size=[0.6, 0.6, 0.6], color="orange")
        clone = viz.clone_object(box)
        viz.set_transform(clone, position=[0.6, 0, 0.3])
        viz.set_color(clone, "blue")
        input("Two boxes. Enter to hide the original. ")
        viz.set_visible(box, False)
        input("One visible box. Enter to delete the clone. ")
        viz.remove(clone)
        print("Original exists:", viz.is_object_alive(box), "Clone exists:", viz.is_object_alive(clone))
        input("Enter to clear the scene. ")
        viz.clear()
        print("Remaining objects:", len(viz.get_display_state()["objects"]))
        input("Enter to exit. ")
    finally:
        viz.close()


if __name__ == "__main__":
    main()
