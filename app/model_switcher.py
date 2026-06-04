"""
Live2D model reload helper - releases old model and loads new one.
"""

import os
import live2d.v3 as live2d


def reload_live2d_model(desk, new_model_path: str) -> bool:
    """Release old model, load new one. Returns success."""
    if not os.path.isfile(new_model_path):
        print(f"[ModelSwitcher] Model file not found: {new_model_path}")
        return False

    old_path = getattr(desk, "model_path", "")
    print(f"[ModelSwitcher] Switching Live2D model: {old_path} -> {new_model_path}")

    # Ensure we have a valid OpenGL context before any Live2D operations
    gl_widget = None
    if hasattr(desk, "_window") and desk._window is not None:
        gl_widget = getattr(desk._window, "_gl", None)

    # Make the OpenGL context current before releasing old model
    if gl_widget is not None:
        try:
            gl_widget.makeCurrent()
        except Exception:
            pass

    if getattr(desk, "_model", None) is not None:
        try:
            live2d.glRelease()
        except Exception:
            pass
        # IMPORTANT: Do NOT call live2d.dispose() here.
        # dispose() destroys the entire CubismFramework, requiring re-init.
        # Just release the Python reference so GC cleans up the C++ model.
        desk._model = None

    desk.model_path = os.path.normpath(new_model_path)

    try:
        desk._init_model_gl()
        if getattr(desk, "_model", None) is None:
            raise RuntimeError("Live2D model init returned no model")
        print(f"[ModelSwitcher] Model loaded: {new_model_path}")
        return True
    except Exception as exc:
        print(f"[ModelSwitcher] Model load failed: {exc}")
        import traceback
        traceback.print_exc()
        # Try to rollback to previous model
        if old_path and os.path.isfile(old_path):
            print(f"[ModelSwitcher] Rolling back to: {old_path}")
            desk.model_path = os.path.normpath(old_path)
            try:
                desk._init_model_gl()
                if getattr(desk, "_model", None) is None:
                    raise RuntimeError("Live2D rollback init returned no model")
                print(f"[ModelSwitcher] Rollback successful")
            except Exception:
                print(f"[ModelSwitcher] Rollback also failed")
        return False
