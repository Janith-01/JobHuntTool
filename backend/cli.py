"""
CLI entry point for JobHuntTool.
Provides command-line interface to run scrapers and manage the pipeline.

Usage:
    python -m backend.cli scrape --query "Software Intern" --location "Sri Lanka"
    python -m backend.cli scrape --platform linkedin --max-results 20
    python -m backend.cli stats
    python -m backend.cli server
"""

import argparse
import asyncio
import logging
import sys

from backend.config import settings
from backend.database.connection import Database
from backend.database.models import SourcePlatform
from backend.scrapers.orchestrator import ScraperOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="JobHuntTool",
        description="🎯 Intelligent Job Scraping & Application Management Tool",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── Scrape Command ───────────────────────────────────────
    scrape_parser = subparsers.add_parser("scrape", help="Run job scrapers")
    scrape_parser.add_argument(
        "-q", "--query",
        default="Software Intern",
        help="Search query (default: 'Software Intern')"
    )
    scrape_parser.add_argument(
        "-l", "--location",
        default="Sri Lanka",
        help="Target location (default: 'Sri Lanka')"
    )
    scrape_parser.add_argument(
        "-p", "--platform",
        choices=[p.value for p in SourcePlatform],
        help="Specific platform to scrape (default: all)"
    )
    scrape_parser.add_argument(
        "-m", "--max-results",
        type=int, default=30,
        help="Max results per platform (default: 30)"
    )
    scrape_parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window during scraping"
    )
    scrape_parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run scrapers sequentially instead of concurrently"
    )

    # ── Stats Command ────────────────────────────────────────
    subparsers.add_parser("stats", help="Show database statistics")

    # ── Server Command ───────────────────────────────────────
    server_parser = subparsers.add_parser("server", help="Start the API server")
    server_parser.add_argument(
        "--port", type=int, default=settings.API_PORT,
        help=f"Server port (default: {settings.API_PORT})"
    )
    server_parser.add_argument(
        "--reload", action="store_true",
        help="Enable auto-reload for development"
    )

    # ── Init Command ─────────────────────────────────────────
    subparsers.add_parser("init", help="Initialize database and install Playwright browsers")

    return parser


async def cmd_scrape(args):
    """Execute the scraping command."""
    orchestrator = ScraperOrchestrator()

    platforms = None
    if args.platform:
        platforms = [SourcePlatform(args.platform)]

    await orchestrator.run_all(
        search_query=args.query,
        location=args.location,
        max_results_per_platform=args.max_results,
        platforms=platforms,
        headless=not args.no_headless,
        concurrent=not args.sequential,
    )


async def cmd_stats(args):
    """Show database statistics."""
    db = Database.get_async_db()

    total = await db.jobs.count_documents({})
    print(f"\n📊 Database Statistics")
    print(f"{'─' * 40}")
    print(f"  Total jobs: {total}")

    # Status breakdown
    pipeline = [{"$group": {"_id": "$application_status", "count": {"$sum": 1}}}]
    print(f"\n  Status Breakdown:")
    async for doc in db.jobs.aggregate(pipeline):
        print(f"    {doc['_id']:<25} {doc['count']:>5}")

    # Platform breakdown
    pipeline = [{"$group": {"_id": "$source_platform", "count": {"$sum": 1}}}]
    print(f"\n  Platform Breakdown:")
    async for doc in db.jobs.aggregate(pipeline):
        print(f"    {doc['_id']:<25} {doc['count']:>5}")

    # Recent additions
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent = await db.jobs.count_documents({"scraped_at": {"$gte": week_ago}})
    print(f"\n  Jobs added (last 7 days): {recent}")
    print(f"{'─' * 40}\n")


def cmd_server(args):
    """Start the FastAPI server."""
    import uvicorn

    # ── Fix for Python 3.14+ on Windows ─────────────────────
    # Python 3.14 defaults to SelectorEventLoop on Windows, which
    # does NOT support subprocess_exec (needed by Playwright).
    # We must set ProactorEventLoopPolicy BEFORE uvicorn.run()
    # so Uvicorn creates a ProactorEventLoop.
    if sys.platform == "win32":
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    uvicorn.run(
        "backend.api:app",
        host="0.0.0.0",
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


async def cmd_init(args):
    """Initialize the project - install browsers and set up DB."""
    import subprocess

    print("🔧 Initializing JobHuntTool...")

    # Install Playwright browsers
    print("\n📦 Installing Playwright browsers...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)

    # Test database connection
    print("\n🔌 Testing MongoDB connection...")
    connected = await Database.ping_async()
    if connected:
        await Database.create_indexes()
        print("✅ Database connected and indexes created")
    else:
        print("⚠️ MongoDB not available - make sure it's running")

    # Create directories
    settings.ensure_directories()
    print("📁 Output directories created")

    print("\n✅ Initialization complete!")
    print(f"   Run 'python -m backend.cli server' to start the API")
    print(f"   Run 'python -m backend.cli scrape' to start scraping")


def main():
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "scrape":
        asyncio.run(cmd_scrape(args))
    elif args.command == "stats":
        asyncio.run(cmd_stats(args))
    elif args.command == "server":
        cmd_server(args)
    elif args.command == "init":
        asyncio.run(cmd_init(args))


if __name__ == "__main__":
    main()
