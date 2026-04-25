from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol, cast

from redis import Redis


class CacheStore(Protocol):
    def get_json(self, key: str) -> dict[str, object] | None:
        ...

    def set_json(self, key: str, value: dict[str, object], ttl_seconds: int) -> None:
        ...

    def delete(self, key: str) -> None:
        ...


@dataclass(slots=True)
class MemoryCacheStore:
    values: dict[str, dict[str, object]] = field(default_factory=dict)

    def get_json(self, key: str) -> dict[str, object] | None:
        return self.values.get(key)

    def set_json(self, key: str, value: dict[str, object], ttl_seconds: int) -> None:
        del ttl_seconds
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


@dataclass(slots=True)
class RedisCacheStore:
    client: Redis

    def get_json(self, key: str) -> dict[str, object] | None:
        raw = cast(str | None, self.client.get(key))
        if raw is None:
            return None
        return cast(dict[str, object], json.loads(raw))

    def set_json(self, key: str, value: dict[str, object], ttl_seconds: int) -> None:
        self.client.set(key, json.dumps(value), ex=timedelta(seconds=ttl_seconds))

    def delete(self, key: str) -> None:
        self.client.delete(key)


def build_cache_store(redis_url: str) -> CacheStore:
    if redis_url.startswith("memory://"):
        return MemoryCacheStore()
    return RedisCacheStore(client=Redis.from_url(redis_url, decode_responses=True))
