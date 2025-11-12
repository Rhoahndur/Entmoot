"""
Background service for cleaning up expired uploaded files.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from entmoot.core.config import settings
from entmoot.core.storage import storage_service

logger = logging.getLogger(__name__)


class CleanupService:
    """
    Service for automatic cleanup of expired uploaded files.

    This service runs as a background task and periodically removes
    uploaded files that exceed the retention period.
    """

    def __init__(
        self,
        retention_hours: Optional[int] = None,
        cleanup_interval_minutes: int = 60,
    ) -> None:
        """
        Initialize the cleanup service.

        Args:
            retention_hours: Hours to retain files before deletion (defaults to settings)
            cleanup_interval_minutes: Minutes between cleanup runs
        """
        self.retention_hours = retention_hours or settings.upload_retention_hours
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self._task: Optional[asyncio.Task] = None  # type: ignore
        self._running = False
        logger.info(
            f"CleanupService initialized: retention={self.retention_hours}h, "
            f"interval={self.cleanup_interval_minutes}m"
        )

    async def cleanup_expired_files(self) -> dict[str, int]:
        """
        Clean up files that have exceeded the retention period.

        This method:
        1. Lists all uploads
        2. Checks metadata for upload time
        3. Deletes uploads older than retention period
        4. Skips files currently being processed (status != COMPLETED)

        Returns:
            Dictionary with cleanup statistics:
            - checked: Number of uploads checked
            - deleted: Number of uploads deleted
            - errors: Number of errors encountered
        """
        stats = {"checked": 0, "deleted": 0, "errors": 0}

        try:
            # Calculate cutoff time
            cutoff_time = datetime.utcnow() - timedelta(hours=self.retention_hours)
            logger.info(f"Starting cleanup: cutoff time = {cutoff_time.isoformat()}")

            # Get all upload IDs
            upload_ids = await storage_service.list_uploads()
            stats["checked"] = len(upload_ids)
            logger.debug(f"Found {len(upload_ids)} uploads to check")

            # Check each upload
            for upload_id in upload_ids:
                try:
                    # Get metadata
                    metadata = await storage_service.get_metadata(upload_id)

                    if not metadata:
                        logger.warning(f"No metadata found for {upload_id}, skipping")
                        continue

                    # Check if file is expired
                    if metadata.upload_time < cutoff_time:
                        # Verify file is not in use (only delete completed uploads)
                        if metadata.status.value in ["completed", "failed"]:
                            logger.info(
                                f"Deleting expired upload {upload_id}: "
                                f"uploaded {metadata.upload_time.isoformat()}"
                            )
                            success = await storage_service.delete_upload(upload_id)
                            if success:
                                stats["deleted"] += 1
                            else:
                                stats["errors"] += 1
                        else:
                            logger.debug(
                                f"Skipping {upload_id}: status={metadata.status.value} "
                                "(not completed/failed)"
                            )

                except Exception as e:
                    logger.error(f"Error processing upload {upload_id}: {e}")
                    stats["errors"] += 1

            logger.info(
                f"Cleanup completed: checked={stats['checked']}, "
                f"deleted={stats['deleted']}, errors={stats['errors']}"
            )

        except Exception as e:
            logger.error(f"Cleanup task failed: {e}", exc_info=True)
            stats["errors"] += 1

        return stats

    async def _cleanup_loop(self) -> None:
        """
        Main cleanup loop that runs periodically.

        This loop runs continuously until stopped, performing cleanup
        at the specified interval.
        """
        logger.info("Cleanup loop started")

        while self._running:
            try:
                # Perform cleanup
                await self.cleanup_expired_files()

                # Wait for next interval
                await asyncio.sleep(self.cleanup_interval_minutes * 60)

            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in cleanup loop: {e}", exc_info=True)
                # Wait a bit before retrying to avoid rapid error loops
                await asyncio.sleep(60)

        logger.info("Cleanup loop stopped")

    async def start(self) -> None:
        """
        Start the cleanup service.

        Creates a background task that runs the cleanup loop.
        """
        if self._running:
            logger.warning("Cleanup service is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info("Cleanup service started")

    async def stop(self) -> None:
        """
        Stop the cleanup service.

        Cancels the background task and waits for it to complete.
        """
        if not self._running:
            logger.warning("Cleanup service is not running")
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Cleanup service stopped")

    async def run_once(self) -> dict[str, int]:
        """
        Run cleanup once without starting the background loop.

        Useful for manual cleanup or testing.

        Returns:
            Cleanup statistics dictionary
        """
        logger.info("Running one-time cleanup")
        return await self.cleanup_expired_files()


# Global cleanup service instance
cleanup_service = CleanupService()
