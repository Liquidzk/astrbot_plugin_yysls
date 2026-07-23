from __future__ import annotations

import asyncio
import time
from typing import Any

import aiohttp

from .models import (
    RankBoard,
    RankSnapshot,
    format_snapshot_time,
    parse_entries,
    select_latest_four_periods,
)


class RankApiError(RuntimeError):
    pass


class RankService:
    API_BASE = "https://yysls.rubysiu.cn/prod-api/"
    ACTIVE_PERIODS_PATH = "yysls/period/active/with-dungeon"
    RANK_PATH = "yysls/public/rank/realtime/{period_id}"

    def __init__(self, cache_seconds: int = 60):
        self.cache_seconds = cache_seconds
        self._cached: RankSnapshot | None = None
        self._cached_at = 0.0
        self._lock = asyncio.Lock()

    async def get_latest(self) -> RankSnapshot:
        now = time.monotonic()
        if self._cached and now - self._cached_at < self.cache_seconds:
            return self._cached

        async with self._lock:
            now = time.monotonic()
            if self._cached and now - self._cached_at < self.cache_seconds:
                return self._cached

            snapshot = await self._fetch_latest()
            self._cached = snapshot
            self._cached_at = time.monotonic()
            return snapshot

    async def _fetch_latest(self) -> RankSnapshot:
        timeout = aiohttp.ClientTimeout(total=15, connect=5)
        headers = {
            "Accept": "application/json",
            "Referer": "https://yysls.rubysiu.cn/yysls/rank",
            "User-Agent": "AstrBot-YanyunRank/0.1 (+https://github.com/Liquidzk/astrbot_plugin_yysls)",
        }
        try:
            async with aiohttp.ClientSession(
                base_url=self.API_BASE,
                timeout=timeout,
                headers=headers,
            ) as session:
                period_data = await self._get_data(session, self.ACTIVE_PERIODS_PATH)
                if not isinstance(period_data, list):
                    raise RankApiError("活动周期接口返回了无效数据")
                try:
                    periods = select_latest_four_periods(period_data)
                except ValueError as exc:
                    raise RankApiError(str(exc)) from exc

                rank_values = await asyncio.gather(
                    *(
                        self._get_data(
                            session,
                            self.RANK_PATH.format(period_id=period.id),
                        )
                        for period in periods
                    )
                )
        except RankApiError:
            raise
        except TimeoutError as exc:
            raise RankApiError("数据源请求超时") from exc
        except aiohttp.ClientError as exc:
            raise RankApiError("暂时无法连接数据源") from exc

        boards: list[RankBoard] = []
        snapshot_times: list[str] = []
        for period, values in zip(periods, rank_values, strict=True):
            if not isinstance(values, list):
                raise RankApiError(f"{period.period_name} 返回了无效排名")
            try:
                entries = parse_entries(values)
            except ValueError as exc:
                raise RankApiError(f"{period.period_name} 的排名格式无效") from exc
            if not entries:
                raise RankApiError(f"{period.period_name} 暂无排名数据")
            boards.append(RankBoard(period=period, entries=entries))
            snapshot_times.extend(entry.snapshot_time for entry in entries)

        updated_at = format_snapshot_time(max(snapshot_times, default=""))
        return RankSnapshot(boards=tuple(boards), updated_at=updated_at)

    @staticmethod
    async def _get_data(
        session: aiohttp.ClientSession,
        path: str,
    ) -> Any:
        async with session.get(path) as response:
            if response.status != 200:
                raise RankApiError(f"数据源返回 HTTP {response.status}")
            try:
                payload = await response.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError) as exc:
                raise RankApiError("数据源没有返回 JSON") from exc

        if not isinstance(payload, dict) or int(payload.get("code", 0)) != 200:
            message = payload.get("msg") if isinstance(payload, dict) else None
            raise RankApiError(str(message or "数据源返回失败"))
        return payload.get("data")
