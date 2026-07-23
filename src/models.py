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
    start_duration: str
    end_duration: str
    team_count: int

    @property
    def rank_label(self) -> str:
        if self.start_rank == self.end_rank:
            return str(self.start_rank)
        return f"{self.start_rank}-{self.end_rank}"

    @property
    def duration_label(self) -> str:
        start = compact_duration(self.start_duration)
        end = compact_duration(self.end_duration)
        if start == end:
            return start
        return f"{start}-{end}"


@dataclass(frozen=True)
class RankPosition:
    start_rank: int
    end_rank: int
    exact: bool
    total_entries: int

    @property
    def rank_label(self) -> str:
        if self.start_rank == self.end_rank:
            return str(self.start_rank)
        return f"{self.start_rank}-{self.end_rank}"

    @property
    def team_count(self) -> int:
        return self.end_rank - self.start_rank + 1


@dataclass(frozen=True)
class RankBoard:
    period: Period
    entries: tuple[RankingEntry, ...]

    def top_entries(self, limit: int = 20) -> tuple[RankingEntry, ...]:
        return self.entries[:limit]

    def aggregate_tail(self, top_limit: int = 20) -> tuple[RankAggregate, ...]:
        max_span_seconds = 3 if self.period.period_type == 1 else 6
        return aggregate_entries(
            self.entries[top_limit:],
            max_span_seconds=max_span_seconds,
        )


@dataclass(frozen=True)
class RankSnapshot:
    boards: tuple[RankBoard, ...]
    updated_at: str
    source: str = "网站排行榜"


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
    max_span_seconds: int = 3,
    minimum_teams: int = 5,
    target_teams: int = 20,
) -> tuple[RankAggregate, ...]:
    if not entries:
        return ()

    second_groups: list[RankAggregate] = []
    for entry in entries:
        previous = second_groups[-1] if second_groups else None
        if (
            previous
            and previous.end_duration == entry.duration
            and previous.end_rank + 1 == entry.rank
        ):
            second_groups[-1] = RankAggregate(
                start_rank=previous.start_rank,
                end_rank=entry.rank,
                start_duration=previous.start_duration,
                end_duration=entry.duration,
                team_count=previous.team_count + 1,
            )
        else:
            second_groups.append(
                RankAggregate(
                    start_rank=entry.rank,
                    end_rank=entry.rank,
                    start_duration=entry.duration,
                    end_duration=entry.duration,
                    team_count=1,
                )
            )

    aggregates: list[RankAggregate] = []
    pending: RankAggregate | None = None
    for group in second_groups:
        pending = _merge_aggregates(pending, group)
        span_seconds = (
            duration_to_seconds(pending.end_duration)
            - duration_to_seconds(pending.start_duration)
        )
        should_close = (
            pending.team_count >= minimum_teams
            and (
                span_seconds >= max_span_seconds
                or pending.team_count >= target_teams
            )
        )
        if should_close:
            aggregates.append(pending)
            pending = None

    if pending:
        if aggregates:
            aggregates[-1] = _merge_aggregates(aggregates[-1], pending)
        else:
            aggregates.append(pending)
    return tuple(aggregates)


def _merge_aggregates(
    left: RankAggregate | None,
    right: RankAggregate,
) -> RankAggregate:
    if left is None:
        return right
    return RankAggregate(
        start_rank=left.start_rank,
        end_rank=right.end_rank,
        start_duration=left.start_duration,
        end_duration=right.end_duration,
        team_count=left.team_count + right.team_count,
    )


def duration_to_seconds(value: str) -> int:
    numbers = re.findall(r"\d+", value)
    if len(numbers) < 2:
        raise ValueError(f"无法解析用时：{value}")
    return int(numbers[0]) * 60 + int(numbers[1])


def parse_query_duration(value: str) -> int:
    match = re.fullmatch(r"\s*(\d{1,3})[:：]([0-5]\d)\s*", value)
    if match is None:
        raise ValueError("时间格式应为 分:秒，例如 7:11")
    return int(match.group(1)) * 60 + int(match.group(2))


def format_duration_seconds(total_seconds: int) -> str:
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def lookup_duration_rank(
    entries: tuple[RankingEntry, ...],
    target_seconds: int,
) -> RankPosition:
    if not entries:
        raise ValueError("榜单暂无排名数据")

    ranked_durations = tuple(
        (entry.rank, duration_to_seconds(entry.duration))
        for entry in entries
    )
    matching_ranks = tuple(
        rank
        for rank, duration_seconds in ranked_durations
        if duration_seconds == target_seconds
    )
    if matching_ranks:
        return RankPosition(
            start_rank=min(matching_ranks),
            end_rank=max(matching_ranks),
            exact=True,
            total_entries=len(entries),
        )

    projected_rank = (
        sum(
            duration_seconds < target_seconds
            for _, duration_seconds in ranked_durations
        )
        + 1
    )
    return RankPosition(
        start_rank=projected_rank,
        end_rank=projected_rank,
        exact=False,
        total_entries=len(entries),
    )


def compact_duration(value: str) -> str:
    try:
        total_seconds = duration_to_seconds(value)
    except ValueError:
        return value
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def format_snapshot_time(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return value or "未知"
