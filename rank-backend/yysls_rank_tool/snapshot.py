from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import time
from typing import Any

from .collector import (
    DEFAULT_HOSTNUM,
    DEFAULT_PID,
    FetchOptions,
    ProtocolError,
    YyslsClient,
    format_duration,
    get_base,
    merge_player_info_from_rank,
    write_json,
)


@dataclass(frozen=True)
class BoardSpec:
    rank_name: str
    period_id: int
    dungeon_id: int
    dungeon_name: str
    dungeon_type: int
    period_type: int
    period_order: int

    @property
    def team_size_name(self) -> str:
        return "十人" if self.dungeon_type == 1 else "五人"

    @property
    def difficulty_name(self) -> str:
        return "普通" if self.period_type == 1 else "挑战"

    def period_payload(self) -> dict[str, Any]:
        period_name = (
            f"{self.dungeon_name} {self.difficulty_name}"
            f"第{self.period_order}期"
        )
        return {
            "id": self.period_id,
            "dungeonId": self.dungeon_id,
            "dungeonName": self.dungeon_name,
            "dungeonType": self.dungeon_type,
            "periodName": period_name,
            "periodType": self.period_type,
            "periodOrder": self.period_order,
            "seasonId": 0,
            "startTime": "-",
            "endTime": "-",
        }


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "ranks.json"


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} 必须是正整数")
    return value


def load_board_specs(path: Path) -> tuple[BoardSpec, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"无法读取榜单配置：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"榜单配置不是有效 JSON：{path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("榜单配置根节点必须是对象")
    period_order = _positive_int(
        payload.get("periodOrder"),
        "periodOrder",
    )

    boards = []
    team_configs = (
        ("ten", 1, 10, "rank_team10_dungeon_"),
        ("five", 2, 5, "rank_team_dungeon_"),
    )
    difficulty_configs = (
        ("normalRankId", 1),
        ("challengeRankId", 2),
    )
    for team_key, dungeon_type, dungeon_id, rank_prefix in team_configs:
        team_value = payload.get(team_key)
        if not isinstance(team_value, dict):
            raise ValueError(f"{team_key} 必须是对象")
        dungeon_name = team_value.get("dungeonName")
        if not isinstance(dungeon_name, str) or not dungeon_name.strip():
            raise ValueError(f"{team_key}.dungeonName 不能为空")

        for rank_id_key, period_type in difficulty_configs:
            rank_id = _positive_int(
                team_value.get(rank_id_key),
                f"{team_key}.{rank_id_key}",
            )
            boards.append(
                BoardSpec(
                    rank_name=f"{rank_prefix}{rank_id}",
                    period_id=rank_id,
                    dungeon_id=dungeon_id,
                    dungeon_name=dungeon_name.strip(),
                    dungeon_type=dungeon_type,
                    period_type=period_type,
                    period_order=period_order,
                )
            )
    return tuple(boards)


def leader_name(
    entry: dict[str, Any],
    embedded_players: dict[str, dict[str, Any]],
) -> str:
    details = entry.get("ud")
    details = details if isinstance(details, dict) else {}
    leader_id = details.get("leader_id")
    player = embedded_players.get(leader_id, {})
    nickname = get_base(player).get("nickname")
    if isinstance(nickname, str) and nickname.strip():
        return nickname.strip()
    return "匿名队伍"


def convert_entries(
    entries: list[dict[str, Any]],
    snapshot_time: str,
) -> list[dict[str, Any]]:
    embedded_players = merge_player_info_from_rank(entries)
    converted = []
    for rank, entry in enumerate(entries, start=1):
        converted.append(
            {
                "rank": rank,
                "teamName": leader_name(entry, embedded_players),
                "durationStr": format_duration(entry.get("score")),
                "snapshotTime": snapshot_time,
            }
        )
    return converted


def collect_snapshot(
    client: YyslsClient,
    boards: tuple[BoardSpec, ...],
) -> dict[str, Any]:
    captured = datetime.now().astimezone()
    snapshot_time = captured.strftime("%Y%m%d%H%M%S")
    output_boards = []

    for board in boards:
        print(
            f"Fetching {board.team_size_name}{board.difficulty_name} "
            f"({board.rank_name})..."
        )
        entries, metadata = client.fetch_all_rank_pages(
            board.rank_name,
            raw_pages_dir=None,
        )
        expected_total = metadata.get("rank_total_len")
        if not entries:
            raise ProtocolError(f"{board.rank_name} returned no entries")
        if isinstance(expected_total, int) and len(entries) != expected_total:
            raise ProtocolError(
                f"{board.rank_name} returned {len(entries)}/"
                f"{expected_total} entries"
            )

        output_boards.append(
            {
                "rankName": board.rank_name,
                "reportedTotal": expected_total,
                "period": board.period_payload(),
                "entries": convert_entries(entries, snapshot_time),
            }
        )

    return {
        "schemaVersion": 1,
        "source": "netease-public-rank",
        "capturedAt": captured.isoformat(timespec="seconds"),
        "updatedAt": captured.strftime("%Y-%m-%d %H:%M"),
        "boards": output_boards,
    }


def write_snapshot_atomic(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    write_json(temporary_path, snapshot)
    os.replace(temporary_path, path)


def default_output_path() -> Path:
    plugin_root = Path(__file__).resolve().parents[2]
    return plugin_root / "data" / "current-ranks.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh the configured Yanyun rank snapshot."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config_path(),
        help="JSON file containing period and rank IDs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output_path(),
        help="Stable JSON snapshot path used by the AstrBot plugin.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Refresh interval in seconds; 0 runs once.",
    )
    parser.add_argument("--pid", default=DEFAULT_PID)
    parser.add_argument("--hostnum", type=int, default=DEFAULT_HOSTNUM)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args()


def refresh_once(args: argparse.Namespace) -> None:
    boards = load_board_specs(args.config)
    print(f"Loaded rank config: {args.config}")
    options = FetchOptions(
        delay_seconds=max(args.delay, 0.2),
        max_pages=None,
        player_batch_size=40,
        retries=max(1, args.retries),
    )
    with YyslsClient(
        pid=args.pid,
        hostnum=args.hostnum,
        options=options,
    ) as client:
        snapshot = collect_snapshot(client, boards)
    write_snapshot_atomic(args.output, snapshot)
    print(
        f"Snapshot updated: {snapshot['updatedAt']} -> "
        f"{args.output}"
    )


def main() -> None:
    args = parse_args()
    interval = max(0, args.interval)

    while True:
        started_at = time.monotonic()
        try:
            refresh_once(args)
        except Exception as exc:
            print(
                f"Snapshot refresh failed: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            if interval == 0:
                raise

        if interval == 0:
            return
        elapsed = time.monotonic() - started_at
        time.sleep(max(1, interval - elapsed))
