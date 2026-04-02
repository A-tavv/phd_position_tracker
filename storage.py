import hashlib
import logging
from typing import Optional

import redis

import config


class RedisSeenJobsStore:
    def __init__(self, redis_url: str, key_prefix: str, ttl_seconds: int):
        self.redis_url = redis_url.strip()
        self.key_prefix = key_prefix.strip() or "phd_tracker:seen"
        self.ttl_seconds = max(1, ttl_seconds)
        self.client: Optional[redis.Redis] = None

        if not self.redis_url:
            logging.warning("REDIS_URL is not configured. Seen-job tracking is disabled.")
            return

        self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)

    def _build_key(self, job_id: str) -> str:
        digest = hashlib.sha256(job_id.strip().encode("utf-8")).hexdigest()
        return f"{self.key_prefix}:{digest}"

    def mark_if_new(self, job_id: str) -> bool:
        if not self.client:
            return True

        key = self._build_key(job_id)
        return bool(self.client.set(key, "1", nx=True, ex=self.ttl_seconds))


def get_seen_jobs_store() -> RedisSeenJobsStore:
    return RedisSeenJobsStore(
        config.REDIS_URL,
        config.REDIS_KEY_PREFIX,
        config.SEEN_JOB_TTL_SECONDS,
    )
