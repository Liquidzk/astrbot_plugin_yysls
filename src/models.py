from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any


def _clean_text(value: Any, fallback: str = "-") -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text or fallback


@dataclass(frozen=True)
class Period:
    id: int
    dungeon_id: int
    dungeon_name: str
    dungeon_type: int
    period_name: str
    period_type: int
    period_order: int
    season_id: int
    start_time: str
    end_time: str

    @classmethod
    def from_api(cls, value: dict[str, Any]) -> "Period":
        try:
            return cls(
                id=int(value["id"]),
                dungeon_id=int(value["dungeonId"]),
                dungeon_name=_clean_text(value.get("dungeonName"), "未知副本"),
                dungeon_type=int(value.get("dungeonType") or 0),
                period_name=_clean_text(value.get("periodName"), "未命名周期"),
                period_type=int(value.get("periodType") or 0),
                period_order=int(value.get("periodOrder") or 0),
                season_id=int(value.get("seasonId") or 0),
                start_time=_clean_text(value.get("startTime")),
                end_time=_clean_text(value.get("endTime")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("活动周期数据格式无效") from exc

    @property
    def difficulty_name(self) -> str:
        return {1: "普通", 2: "挑战"}.get(self.period_type, "其他")

    @property
    def team_size_name(self) -> str:
        return {1: "十人", 2: "五人"}.get(self.dungeon_type, "其他")


@dataclass(frozen=True)
class RankingEntry:
    rank: int
    team_name: str
    duration: str
    snapshot_time: str

    @classmethod
    def from_api(cls, value: dict[str, Any]) -> "RankingEntry":
        try:
            return cls(
                rank=int(value["rank"]),
                team_name=_clean_text(value.get("teamName"), "匿名队伍"),
                duration=_clean_text(value.get("durationStr")),
                snapshot_time=_clean_text(value.get("snapshotTime")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("排名数据格式无效") from exc


@dataclass(frozen=True)
class RankAggregate:
    start_rank: int
    end_rank: int
    duration: str

    @property
    def rank_label(self) -> str:
        if self.start_rank == self.end_rank:
            return str(self.start_rank)
        return f"{self.start_rank}-{self.end_rank}"


@dataclass(frozen=True)
class RankBoard:
    period: Period
    entries: tuple[RankingEntry, ...]

    def top_entries(self, limit: int = 20) -> tuple[RankingEntry, ...]:
        return self.entries[:limit]

    def aggregate_tail(self, top_limit: int = 20) -> tuple[RankAggregate, ...]:
        return aggregate_entries(self.entries[top_limit:])


@dataclass(frozen=True)
class RankSnapshot:
    boards: tuple[RankBoard, ...]
    updated_at: str


def select_latest_four_periods(values: list[dict[str, Any]]) -> tuple[Period, ...]:
    periods = [Period.from_api(value) for value in values]
    if not periods:
        raise ValueError("当前没有活动中的排行榜")

    latest_season = max(period.season_id for period in periods)
    periods = [period for period in periods if period.season_id == latest_season]

    latest_by_board: dict[tuple[int, int], Period] = {}
    for period in periods:
        key = (period.dungeon_id, period.period_type)
        current = latest_by_board.get(key)
        if current is None or (
            period.period_order,
            period.start_time,
            period.id,
        ) > (
            current.period_order,
            current.start_time,
            current.id,
        ):
            latest_by_board[key] = period

    selected = sorted(
        latest_by_board.values(),
        key=lambda period: (
            period.dungeon_type,
            period.dungeon_id,
            period.period_type,
        ),
    )
    if len(selected) != 4:
        raise ValueError(f"当前活动榜单数量为 {len(selected)}，预期为 4")
    return tuple(selected)


def parse_entries(
    values: list[dict[str, Any]],
    limit: int | None = None,
) -> tuple[RankingEntry, ...]:
    entries = [RankingEntry.from_api(value) for value in values]
    entries.sort(key=lambda entry: entry.rank)
    if limit is not None:
        entries = entries[:limit]
    return tuple(entries)


def aggregate_entries(
    entries: tuple[RankingEntry, ...],
) -> tuple[RankAggregate, ...]:
    aggregates: list[RankAggregate] = []
    for entry in entries:
        previous = aggregates[-1] if aggregates else None
        if (
            previous
            and previous.duration == entry.duration
            and previous.end_rank + 1 == entry.rank
        ):
            aggregates[-1] = RankAggregate(
                start_rank=previous.start_rank,
                end_rank=entry.rank,
                duration=previous.duration,
            )
        else:
            aggregates.append(
                RankAggregate(
                    start_rank=entry.rank,
                    end_rank=entry.rank,
                    duration=entry.duration,
                )
            )
    return tuple(aggregates)


def compact_duration(value: str) -> str:
    match = re.fullmatch(r"(\d+)分(\d+)秒", value)
    if not match:
        return value
    minutes, seconds = match.groups()
    return f"{int(minutes)}:{int(seconds):02d}"


def format_snapshot_time(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return value or "未知"
