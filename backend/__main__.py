# ── Python 3.14+ Windows fix: must be FIRST ─────────────────
# Set ProactorEventLoop policy before ANY other imports so that
# Uvicorn (and its reloader child processes) get a loop that
# supports subprocess_exec, which Playwright requires.
import sys
if sys.platform == "win32":
    import asyncio
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Allow running as: python -m backend
from backend.cli import main

if __name__ == "__main__":
    main()
