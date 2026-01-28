"""
Activity Reporter
מדווח פעילות משתמשים ל-MongoDB (Best-effort: לא מפיל את הבוט אם יש תקלה)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo import MongoClient

logger = logging.getLogger(__name__)


class ActivityReporter:
    def __init__(self, mongodb_uri: str, service_id: str, service_name: str):
        self._mongodb_uri = mongodb_uri
        self._service_id = service_id
        self._service_name = service_name

        self._client: Optional[MongoClient] = None
        self._collection = None

        self._ensure_connected()

    def _ensure_connected(self):
        if self._collection is not None:
            return

        try:
            self._client = MongoClient(self._mongodb_uri, serverSelectionTimeoutMS=2000)
            db = self._client.get_database("activity_reporter")
            self._collection = db["activities"]
        except Exception as e:
            logger.warning("ActivityReporter init failed: %s", e)
            self._collection = None

    def report_activity(self, user_id: int):
        try:
            if self._collection is None:
                self._ensure_connected()
            if self._collection is None:
                return

            self._collection.insert_one({
                "service_id": self._service_id,
                "service_name": self._service_name,
                "user_id": int(user_id),
                "timestamp": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.debug("ActivityReporter report failed: %s", e)


def create_reporter(mongodb_uri: str, service_id: str, service_name: str) -> ActivityReporter:
    return ActivityReporter(
        mongodb_uri=mongodb_uri,
        service_id=service_id,
        service_name=service_name,
    )

