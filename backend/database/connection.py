"""
MongoDB connection manager using Motor (async MongoDB driver).
Provides both sync (pymongo) and async (motor) connections.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from backend.config import settings
import logging

import certifi

logger = logging.getLogger(__name__)


class Database:
    """Manages MongoDB connections for the application."""

    _async_client: AsyncIOMotorClient | None = None
    _sync_client: MongoClient | None = None

    @classmethod
    def get_async_client(cls) -> AsyncIOMotorClient:
        """Get or create the async Motor client."""
        if cls._async_client is None:
            cls._async_client = AsyncIOMotorClient(
                settings.MONGO_URI,
                tls=True,
                tlsCAFile=certifi.where()
            )
            logger.info(f"Async MongoDB client connected to {settings.MONGO_URI}")
        return cls._async_client

    @classmethod
    def get_sync_client(cls) -> MongoClient:
        """Get or create the sync PyMongo client."""
        if cls._sync_client is None:
            cls._sync_client = MongoClient(
                settings.MONGO_URI,
                tls=True,
                tlsCAFile=certifi.where()
            )
            logger.info(f"Sync MongoDB client connected to {settings.MONGO_URI}")
        return cls._sync_client

    @classmethod
    def get_async_db(cls):
        """Get the async database instance."""
        client = cls.get_async_client()
        return client[settings.MONGO_DB_NAME]

    @classmethod
    def get_sync_db(cls):
        """Get the sync database instance."""
        client = cls.get_sync_client()
        return client[settings.MONGO_DB_NAME]

    @classmethod
    async def ping_async(cls) -> bool:
        """Test async connection to MongoDB."""
        try:
            client = cls.get_async_client()
            await client.admin.command("ping")
            logger.info("✅ Async MongoDB connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ Async MongoDB connection failed: {e}")
            return False

    @classmethod
    def ping_sync(cls) -> bool:
        """Test sync connection to MongoDB."""
        try:
            client = cls.get_sync_client()
            client.admin.command("ping")
            logger.info("✅ Sync MongoDB connection successful")
            return True
        except ConnectionFailure as e:
            logger.error(f"❌ Sync MongoDB connection failed: {e}")
            return False

    @classmethod
    async def close_async(cls):
        """Close the async client connection."""
        if cls._async_client:
            cls._async_client.close()
            cls._async_client = None
            logger.info("Async MongoDB connection closed")

    @classmethod
    def close_sync(cls):
        """Close the sync client connection."""
        if cls._sync_client:
            cls._sync_client.close()
            cls._sync_client = None
            logger.info("Sync MongoDB connection closed")

    @classmethod
    async def create_indexes(cls):
        """Create necessary indexes for optimal query performance."""
        db = cls.get_async_db()

        # Jobs collection indexes
        jobs = db.jobs
        await jobs.create_index("job_id", unique=True)
        await jobs.create_index("company_name")
        await jobs.create_index("application_status")
        await jobs.create_index("source_platform")
        await jobs.create_index("scraped_at")
        await jobs.create_index(
            [("title", "text"), ("job_description", "text"), ("company_name", "text")],
            name="job_text_search"
        )

        # Applications collection indexes
        applications = db.applications
        await applications.create_index("job_id")
        await applications.create_index("status")
        await applications.create_index("applied_at")

        logger.info("✅ Database indexes created successfully")
