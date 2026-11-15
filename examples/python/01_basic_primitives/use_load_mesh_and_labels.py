"""Load a 3D pyramid and compare a model label with text pinned to the window."""

import argparse
from contextlib import nullcontext
from queue import Empty, Queue

import frameviz as fv


def build(viz, url):
    model = viz.load_mesh(url, color=[0.19, 0.52, 0.75], name="Loaded model")
    # A child label follows the model in 3D. The other label uses window pixels.
    viz.add_text_3d("3D label · moves with model", position=[0, 0, 1.0],
                    parent=model, color="black", background_color="rgba(255,255,255,0.9)")
    viz.add_text_2d("Screen label · stays here", x=24, y=65, color="black")
    viz.set_camera_pose([2.3, -3.5, 2.2], [0.25, 0, 0.45])
    return model


def main():
    from serve_sample_mesh import sample_mesh_url

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="Optional HTTP(S) STL or DAE URL")
    args = parser.parse_args()
    source = nullcontext(args.url) if args.url else sample_mesh_url()
    with source as url:
        viz = fv.open(title="Model and labels")
        try:
            viz.set_view_config(background="white", show_axes=False)
            events = Queue()
            for event in ("object_ready", "object_failed"):
                viz.on(event, lambda data, event=event: events.put((event, data)))
            model = build(viz, url)
            try:
                event, data = events.get(timeout=10)
            except Empty:
                parser.exit(1, "The Viewer did not finish loading the model. Check the model URL.\n")
            if event == "object_failed" or data.get("handle") != model:
                parser.exit(1, f"Model failed to load: {data.get('message', 'check the model URL')}\n")
            input("The blue model is ready. Press Enter to move it and its 3D label. ")
            viz.set_transform(model, position=[0.9, 0, 0])
            input("The screen label stays fixed. Press Enter to exit. ")
        finally:
            viz.close()


if __name__ == "__main__":
    main()
