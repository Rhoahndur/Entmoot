"""
Redis storage service for persisting project data across container restarts.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RedisStorage:
    """Redis-based storage for project data and results."""

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis storage client.

        Args:
            redis_url: Redis connection URL. If not provided, uses REDIS_URL env var.
                      Falls back to in-memory dict if Redis is not available.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.client: Optional[redis.Redis] = None
        self.use_fallback = False

        # Fallback to in-memory storage if Redis is not available
        self._fallback_projects: Dict[str, Dict] = {}
        self._fallback_results: Dict[str, str] = {}

        if self.redis_url:
            try:
                self.client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # Test connection
                self.client.ping()
                logger.info("Successfully connected to Redis")
            except (RedisError, Exception) as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory fallback.")
                self.use_fallback = True
        else:
            logger.warning("No REDIS_URL provided. Using in-memory fallback storage.")
            self.use_fallback = True

    # Project metadata operations

    def get_project(self, project_id: str) -> Optional[Dict]:
        """
        Get project metadata.

        Args:
            project_id: Project identifier

        Returns:
            Project metadata dict or None if not found
        """
        try:
            if self.use_fallback:
                return self._fallback_projects.get(project_id)

            key = f"project:{project_id}"
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting project {project_id}: {e}")
            return None

    def set_project(self, project_id: str, data: Dict) -> bool:
        """
        Store project metadata.

        Args:
            project_id: Project identifier
            data: Project metadata dict

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.use_fallback:
                self._fallback_projects[project_id] = data
                return True

            key = f"project:{project_id}"
            self.client.set(key, json.dumps(data))
            return True
        except Exception as e:
            logger.error(f"Error setting project {project_id}: {e}")
            return False

    def delete_project(self, project_id: str) -> bool:
        """
        Delete project metadata.

        Args:
            project_id: Project identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.use_fallback:
                self._fallback_projects.pop(project_id, None)
                return True

            key = f"project:{project_id}"
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {e}")
            return False

    def get_all_projects(self) -> List[Dict]:
        """
        Get all projects.

        Returns:
            List of project metadata dicts
        """
        try:
            if self.use_fallback:
                return list(self._fallback_projects.values())

            projects = []
            # Scan for all project keys
            for key in self.client.scan_iter("project:*"):
                data = self.client.get(key)
                if data:
                    projects.append(json.loads(data))
            return projects
        except Exception as e:
            logger.error(f"Error getting all projects: {e}")
            return []

    def project_exists(self, project_id: str) -> bool:
        """
        Check if project exists.

        Args:
            project_id: Project identifier

        Returns:
            True if project exists, False otherwise
        """
        try:
            if self.use_fallback:
                return project_id in self._fallback_projects

            key = f"project:{project_id}"
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking project existence {project_id}: {e}")
            return False

    # Layout results operations

    def get_results(self, project_id: str) -> Optional[Dict]:
        """
        Get layout results for a project.

        Args:
            project_id: Project identifier

        Returns:
            Layout results dict or None if not found
        """
        try:
            if self.use_fallback:
                data = self._fallback_results.get(project_id)
                return json.loads(data) if data else None

            key = f"results:{project_id}"
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting results for project {project_id}: {e}")
            return None

    def set_results(self, project_id: str, results: Dict) -> bool:
        """
        Store layout results for a project.

        Args:
            project_id: Project identifier
            results: Layout results dict

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.use_fallback:
                self._fallback_results[project_id] = json.dumps(results)
                return True

            key = f"results:{project_id}"
            self.client.set(key, json.dumps(results))
            return True
        except Exception as e:
            logger.error(f"Error setting results for project {project_id}: {e}")
            return False

    def delete_results(self, project_id: str) -> bool:
        """
        Delete layout results for a project.

        Args:
            project_id: Project identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.use_fallback:
                self._fallback_results.pop(project_id, None)
                return True

            key = f"results:{project_id}"
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting results for project {project_id}: {e}")
            return False

    def results_exist(self, project_id: str) -> bool:
        """
        Check if results exist for a project.

        Args:
            project_id: Project identifier

        Returns:
            True if results exist, False otherwise
        """
        try:
            if self.use_fallback:
                return project_id in self._fallback_results

            key = f"results:{project_id}"
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking results existence for project {project_id}: {e}")
            return False


# Global singleton instance
_storage: Optional[RedisStorage] = None


def get_storage() -> RedisStorage:
    """
    Get or create the global Redis storage instance.

    Returns:
        RedisStorage singleton instance
    """
    global _storage
    if _storage is None:
        _storage = RedisStorage()
    return _storage
