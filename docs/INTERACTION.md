# Interaction

Camera controls, picking, and Gizmo transforms are implemented by the TypeScript core. Scene transforms propagate between views of the same scene; camera state stays scoped to the originating view. Keyboard events use `key_down`.

Instance updates of the same size reuse the current object. Resizing transfers current material, alpha, pose, visibility, buffer references, and the live Gizmo target. Model loading and cloning may finish asynchronously; wait for object readiness before treating a handle as rendered.

Acceptance must include real pointer interaction and the resulting authoritative Host state. Calling the same callback programmatically is a useful separate check, but does not prove mouse hit testing or native input behavior.
