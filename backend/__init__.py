# JobHuntTool Backend Package

# ── Python 3.14+ Windows fix ────────────────────────────────
# Must run before Uvicorn creates its event loop.
# In --reload mode, Uvicorn's child process imports backend.api
# which triggers this __init__.py BEFORE the event loop is created.
import sys as _sys
if _sys.platform == "win32":
    import asyncio as _asyncio
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
