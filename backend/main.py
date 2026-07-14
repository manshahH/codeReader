# FastAPI Cloud entrypoint shim.
#
# FastAPI Cloud runs `fastapi run` from the deployed directory. The CLI
# auto-discovers the app by searching for a top-level file that exposes a
# FastAPI instance. Without this shim, the CLI finds backend/app/__init__.py
# (which has no `app` variable) and gives up with "Could not find a default
# file to run".
#
# This file is the conventional discovery target. It simply re-exports the
# real application object so the CLI can locate it while all production code
# stays in app/.
from app.main import app

__all__ = ["app"]
