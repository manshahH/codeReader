"""Deploy shim: re-exports the app so `fastapi run` auto-discovery finds it.

FastAPI Cloud starts the app with the `fastapi` CLI (D-113), which looks for a
module-level `app` at the project root. docs/09 section 1 covers the other half
of this: setuptools must be told `py-modules = ['main']` or the shim is left out
of the wheel entirely and the container cannot boot.

Deliberately nothing but the re-export. This carried a try/except that wrote
'--- LOADING MAIN.PY ---' and an import traceback to stderr while a deploy
import failure was being chased; it outlived that debugging and was the sole
reason CI's `ruff check backend` had been failing (D-128). An unhandled import
error already produces that traceback, and a better one, so the wrapper cost
lint and bought nothing.
"""

from app.main import app

__all__ = ["app"]
