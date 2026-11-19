"""Run from the repository root: python -m backend.app."""
import os

from .hub import build_app


if __name__ == "__main__":
    build_app().run(
        host=os.getenv("WEB_HOST", "0.0.0.0"),
        port=int(os.getenv("WEB_PORT", "5000")),
        debug=False,
        use_reloader=False,
        threaded=True,
    )
