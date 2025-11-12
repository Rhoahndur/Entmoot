"""
USGS elevation data caching system.

Implements two-tier caching:
1. In-memory cache for point queries (30 days TTL)
2. Filesystem cache for DEM tiles (permanent)
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from entmoot.models.elevation import (
    DEMTileMetadata,
    ElevationDataSource,
    ElevationDatum,
    ElevationPoint,
    ElevationUnit,
)

logger = logging.getLogger(__name__)


class ElevationCacheManager:
    """
    Manager for elevation data caching.

    Provides:
    - In-memory cache for point queries
    - Filesystem cache for DEM tiles
    - Cache statistics and maintenance
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        point_cache_ttl: int = 2592000,  # 30 days
        max_memory_entries: int = 10000,
    ) -> None:
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory for filesystem cache
            point_cache_ttl: TTL for point queries in seconds
            max_memory_entries: Maximum entries in memory cache
        """
        self.point_cache_ttl = point_cache_ttl
        self.max_memory_entries = max_memory_entries

        # Set up cache directory
        if cache_dir is None:
            cache_dir = Path.home() / ".entmoot" / "elevation_cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.tiles_dir = self.cache_dir / "tiles"
        self.tiles_dir.mkdir(exist_ok=True)

        self.metadata_dir = self.cache_dir / "metadata"
        self.metadata_dir.mkdir(exist_ok=True)

        # In-memory cache: {cache_key: (ElevationPoint, timestamp)}
        self._point_cache: Dict[str, tuple[ElevationPoint, float]] = {}

        # Tile metadata cache: {tile_id: DEMTileMetadata}
        self._tile_metadata_cache: Dict[str, DEMTileMetadata] = {}

        # Load tile metadata from disk
        self._load_tile_metadata()

        logger.info(
            f"Elevation cache initialized at {self.cache_dir}, "
            f"point TTL: {point_cache_ttl}s, max entries: {max_memory_entries}"
        )

    def _load_tile_metadata(self) -> None:
        """Load tile metadata from disk cache."""
        try:
            metadata_files = list(self.metadata_dir.glob("*.json"))
            for metadata_file in metadata_files:
                try:
                    with open(metadata_file, "r") as f:
                        data = json.load(f)
                        metadata = DEMTileMetadata(**data)
                        self._tile_metadata_cache[metadata.tile_id] = metadata
                except Exception as e:
                    logger.warning(f"Failed to load tile metadata from {metadata_file}: {e}")

            logger.info(f"Loaded {len(self._tile_metadata_cache)} tile metadata entries from cache")
        except Exception as e:
            logger.error(f"Failed to load tile metadata: {e}")

    def get_point(self, cache_key: str) -> Optional[ElevationPoint]:
        """
        Get point from cache.

        Args:
            cache_key: Cache key for the point

        Returns:
            ElevationPoint if cached and not expired, None otherwise
        """
        if cache_key not in self._point_cache:
            return None

        point, timestamp = self._point_cache[cache_key]
        age = time.time() - timestamp

        if age < self.point_cache_ttl:
            logger.debug(f"Point cache hit for key {cache_key[:8]}... (age: {age:.1f}s)")
            return point
        else:
            # Expired
            logger.debug(f"Point cache expired for key {cache_key[:8]}... (age: {age:.1f}s)")
            del self._point_cache[cache_key]
            return None

    def put_point(self, cache_key: str, point: ElevationPoint) -> None:
        """
        Store point in cache.

        Args:
            cache_key: Cache key
            point: ElevationPoint to cache
        """
        # Check if we need to evict old entries
        if len(self._point_cache) >= self.max_memory_entries:
            self._evict_oldest_points()

        self._point_cache[cache_key] = (point, time.time())
        logger.debug(f"Cached point for key {cache_key[:8]}...")

    def _evict_oldest_points(self) -> None:
        """Evict oldest entries from point cache."""
        # Remove 10% of oldest entries
        evict_count = max(1, self.max_memory_entries // 10)

        # Sort by timestamp
        sorted_entries = sorted(self._point_cache.items(), key=lambda x: x[1][1])

        # Remove oldest
        for cache_key, _ in sorted_entries[:evict_count]:
            del self._point_cache[cache_key]

        logger.debug(f"Evicted {evict_count} old entries from point cache")

    def get_tile_metadata(self, tile_id: str) -> Optional[DEMTileMetadata]:
        """
        Get tile metadata from cache.

        Args:
            tile_id: Tile identifier

        Returns:
            DEMTileMetadata if cached, None otherwise
        """
        metadata = self._tile_metadata_cache.get(tile_id)

        if metadata:
            # Update last accessed time
            metadata.last_accessed = datetime.utcnow()
            self._save_tile_metadata(metadata)
            logger.debug(f"Tile metadata cache hit for {tile_id}")

        return metadata

    def put_tile_metadata(self, metadata: DEMTileMetadata) -> None:
        """
        Store tile metadata in cache.

        Args:
            metadata: DEMTileMetadata to cache
        """
        self._tile_metadata_cache[metadata.tile_id] = metadata
        self._save_tile_metadata(metadata)
        logger.debug(f"Cached tile metadata for {metadata.tile_id}")

    def _save_tile_metadata(self, metadata: DEMTileMetadata) -> None:
        """
        Save tile metadata to disk.

        Args:
            metadata: DEMTileMetadata to save
        """
        try:
            metadata_file = self.metadata_dir / f"{metadata.tile_id}.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata.to_dict(), f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save tile metadata for {metadata.tile_id}: {e}")

    def get_tile_path(self, tile_id: str) -> Optional[Path]:
        """
        Get local file path for cached tile.

        Args:
            tile_id: Tile identifier

        Returns:
            Path to tile file if exists, None otherwise
        """
        metadata = self.get_tile_metadata(tile_id)
        if metadata and metadata.file_path:
            tile_path = Path(metadata.file_path)
            if tile_path.exists():
                return tile_path

        return None

    def has_tile(self, tile_id: str) -> bool:
        """
        Check if tile is cached.

        Args:
            tile_id: Tile identifier

        Returns:
            True if tile is cached, False otherwise
        """
        return self.get_tile_path(tile_id) is not None

    def list_tiles(self) -> List[DEMTileMetadata]:
        """
        List all cached tiles.

        Returns:
            List of DEMTileMetadata
        """
        return list(self._tile_metadata_cache.values())

    def clear_point_cache(self) -> int:
        """
        Clear point cache.

        Returns:
            Number of entries cleared
        """
        count = len(self._point_cache)
        self._point_cache.clear()
        logger.info(f"Cleared {count} entries from point cache")
        return count

    def clear_expired_points(self) -> int:
        """
        Clear expired points from cache.

        Returns:
            Number of entries cleared
        """
        now = time.time()
        expired_keys = [
            key
            for key, (_, timestamp) in self._point_cache.items()
            if now - timestamp >= self.point_cache_ttl
        ]

        for key in expired_keys:
            del self._point_cache[key]

        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired entries from point cache")

        return len(expired_keys)

    def delete_tile(self, tile_id: str) -> bool:
        """
        Delete a cached tile.

        Args:
            tile_id: Tile identifier

        Returns:
            True if deleted, False otherwise
        """
        try:
            # Remove from memory cache
            if tile_id in self._tile_metadata_cache:
                metadata = self._tile_metadata_cache[tile_id]

                # Delete tile file
                if metadata.file_path:
                    tile_path = Path(metadata.file_path)
                    if tile_path.exists():
                        tile_path.unlink()

                # Delete metadata file
                metadata_file = self.metadata_dir / f"{tile_id}.json"
                if metadata_file.exists():
                    metadata_file.unlink()

                del self._tile_metadata_cache[tile_id]

                logger.info(f"Deleted cached tile {tile_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete tile {tile_id}: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        # Point cache stats
        point_count = len(self._point_cache)

        # Calculate average age
        if self._point_cache:
            now = time.time()
            ages = [now - timestamp for _, timestamp in self._point_cache.values()]
            avg_age = sum(ages) / len(ages)
        else:
            avg_age = 0.0

        # Tile cache stats
        tile_count = len(self._tile_metadata_cache)
        tile_total_size = 0

        for metadata in self._tile_metadata_cache.values():
            if metadata.file_path:
                tile_path = Path(metadata.file_path)
                if tile_path.exists():
                    tile_total_size += tile_path.stat().st_size

        return {
            "cache_dir": str(self.cache_dir),
            "point_cache": {
                "entries": point_count,
                "max_entries": self.max_memory_entries,
                "ttl_seconds": self.point_cache_ttl,
                "avg_age_seconds": avg_age,
                "fill_percentage": (point_count / self.max_memory_entries) * 100,
            },
            "tile_cache": {
                "tiles": tile_count,
                "total_size_bytes": tile_total_size,
                "total_size_mb": tile_total_size / (1024 * 1024),
                "tiles_dir": str(self.tiles_dir),
                "metadata_dir": str(self.metadata_dir),
            },
        }

    def cleanup_old_tiles(self, days: int = 90) -> int:
        """
        Clean up tiles not accessed in specified days.

        Args:
            days: Number of days of inactivity

        Returns:
            Number of tiles deleted
        """
        cutoff_time = datetime.utcnow().timestamp() - (days * 86400)
        deleted_count = 0

        for tile_id, metadata in list(self._tile_metadata_cache.items()):
            if metadata.last_accessed:
                last_access_time = metadata.last_accessed.timestamp()
                if last_access_time < cutoff_time:
                    if self.delete_tile(tile_id):
                        deleted_count += 1

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} tiles not accessed in {days} days")

        return deleted_count

    def optimize(self) -> Dict[str, int]:
        """
        Optimize cache by clearing expired entries.

        Returns:
            Dictionary with optimization results
        """
        expired_points = self.clear_expired_points()

        return {
            "expired_points_cleared": expired_points,
        }
