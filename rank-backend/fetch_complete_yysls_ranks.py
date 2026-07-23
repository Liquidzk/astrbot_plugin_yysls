from __future__ import annotations

import argparse
import base64
import csv
import json
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx
import msgpack


BASE_URL = "https://h72-ms-prod.netease.com"
RANK_ENDPOINT = "/flk/rank_service/rank_get_ranklist/{rank_name}"
PLAYERS_ENDPOINT = "/flk/redis_player/get_players_info"

DEFAULT_FIELDS = ["base", "head", "identity", "name_card"]

# 来自已成功重放的真实排行榜请求。
DEFAULT_PID = "Z7hbKDFN6oKRkQzM"
DEFAULT_HOSTNUM = 10001

# 可直接修改。截图中已观察到这两个榜单名。
DEFAULT_RANKS = [
    "rank_team_dungeon_60",
    "rank_team10_dungeon_59",
]


class ProtocolError(RuntimeError):
    pass


@dataclass
class FetchOptions:
    delay_seconds: float
    max_pages: int | None
    player_batch_size: int
    retries: int


def make_uid() -> str:
    """生成客户端风格的 16 字符 Base64 请求关联 ID。"""
    return base64.b64encode(secrets.token_bytes(12)).decode("ascii")


def decode_msgpack(data: bytes) -> dict[str, Any]:
    value = msgpack.unpackb(
        data,
        raw=False,
        strict_map_key=False,
    )
    if not isinstance(value, dict):
        raise ProtocolError(
            f"Expected MessagePack map, got {type(value).__name__}"
        )
    return value


def json_default(value: Any) -> str:
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )


def chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def format_duration(score: Any) -> str:
    """
    团本排行榜的负分值目前表现为负完成秒数。
    保留原始 score，同时给出便于阅读的绝对值时间。
    """
    if not isinstance(score, (int, float)):
        return ""

    seconds = abs(float(score))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remainder = seconds % 60

    if hours:
        return f"{hours}:{minutes:02d}:{remainder:06.3f}"
    return f"{minutes}:{remainder:06.3f}"


class YyslsClient:
    def __init__(
        self,
        *,
        pid: str,
        hostnum: int,
        options: FetchOptions,
    ) -> None:
        self.pid = pid
        self.hostnum = hostnum
        self.options = options
        self.http = httpx.Client(
            base_url=BASE_URL,
            timeout=30.0,
            http2=False,
            follow_redirects=False,
            verify=True,
            headers={
                "Content-Type": "application/octet-stream",
                "Accept": "*/*",
                # httpx 会自动解压 gzip，但首次部署使用 identity 更直观。
                "Accept-Encoding": "identity",
                "User-Agent": "yysls-public-rank-collector/1.0",
            },
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "YyslsClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _post_msgpack(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        body = msgpack.packb(payload, use_bin_type=True)
        last_error: Exception | None = None

        for attempt in range(1, self.options.retries + 1):
            try:
                response = self.http.post(path, content=body)
                response.raise_for_status()

                decoded = decode_msgpack(response.content)
                code = decoded.get("code")
                if code != 0:
                    raise ProtocolError(
                        f"Application code={code}, "
                        f"uid={decoded.get('uid')!r}, "
                        f"result={decoded.get('result')!r}"
                    )
                return decoded

            except (httpx.HTTPError, ProtocolError, ValueError) as error:
                last_error = error
                if attempt >= self.options.retries:
                    break

                wait = min(2 ** (attempt - 1), 8)
                print(
                    f"  Request failed ({error}); "
                    f"retrying in {wait}s..."
                )
                time.sleep(wait)

        raise ProtocolError(
            f"Request failed after {self.options.retries} attempts: "
            f"{last_error}"
        )

    def fetch_rank_page(
        self,
        rank_name: str,
        page: int,
    ) -> dict[str, Any]:
        payload = {
            "uid": make_uid(),
            "fields": DEFAULT_FIELDS,
            "pid": self.pid,
            "hostnum": self.hostnum,
            "fuzzy_info": {},
            "rank_name": rank_name,
            "page": page,
            "params": {},
        }

        path = RANK_ENDPOINT.format(rank_name=rank_name)
        response = self._post_msgpack(path, payload)

        result = response.get("result")
        if not isinstance(result, dict):
            raise ProtocolError(
                f"Unexpected rank result for {rank_name}: {result!r}"
            )
        return result

    def fetch_all_rank_pages(
        self,
        rank_name: str,
        raw_pages_dir: Path,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        page = 0
        metadata: dict[str, Any] = {}

        while True:
            if (
                self.options.max_pages is not None
                and page >= self.options.max_pages
            ):
                print(
                    f"  Reached --max-pages={self.options.max_pages}"
                )
                break

            print(f"  Fetching page {page}...")
            result = self.fetch_rank_page(rank_name, page)
            write_json(raw_pages_dir / f"page-{page:03d}.json", result)

            rank_list = result.get("rank_list")
            if not isinstance(rank_list, list):
                raise ProtocolError(
                    f"rank_list is not a list on page {page}"
                )

            for entry in rank_list:
                if isinstance(entry, dict):
                    entries.append(entry)

            metadata = {
                "rank_name": result.get("rank_name", rank_name),
                "rank_total_len": result.get("rank_total_len"),
                "my_rank": result.get("my_rank"),
                "my_data": result.get("my_data"),
                "last_page": page,
                "last_start": result.get("start"),
                "last_end": result.get("end"),
            }

            total = result.get("rank_total_len")
            end = result.get("end")

            print(
                f"    received={len(rank_list)}, "
                f"collected={len(entries)}, total={total}"
            )

            if not rank_list:
                break

            if isinstance(total, int) and len(entries) >= total:
                break

            if isinstance(total, int) and isinstance(end, int) and end >= total:
                break

            page += 1
            time.sleep(self.options.delay_seconds)

        return entries, metadata

    def fetch_players_info(
        self,
        hostnum2pids: dict[int, set[str]],
    ) -> dict[str, dict[str, Any]]:
        pairs: list[tuple[int, str]] = sorted(
            (hostnum, pid)
            for hostnum, pids in hostnum2pids.items()
            for pid in pids
        )

        merged: dict[str, dict[str, Any]] = {}
        batches = list(chunks(pairs, self.options.player_batch_size))

        for batch_index, batch in enumerate(batches, start=1):
            grouped: dict[int, list[str]] = defaultdict(list)
            for hostnum, pid in batch:
                grouped[hostnum].append(pid)

            payload = {
                "fields": DEFAULT_FIELDS,
                "hostnum2pids": dict(grouped),
                "uid": make_uid(),
            }

            print(
                f"  Fetching player batch {batch_index}/{len(batches)} "
                f"({len(batch)} players)..."
            )

            response = self._post_msgpack(
                PLAYERS_ENDPOINT,
                payload,
            )
            result = response.get("result")

            if not isinstance(result, dict):
                raise ProtocolError(
                    f"Unexpected players result: {result!r}"
                )

            for pid, info in result.items():
                if isinstance(pid, str) and isinstance(info, dict):
                    merged[pid] = info

            if batch_index < len(batches):
                time.sleep(self.options.delay_seconds)

        return merged


def merge_player_info_from_rank(
    entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    players: dict[str, dict[str, Any]] = {}

    for entry in entries:
        player_info = entry.get("player_info")
        if not isinstance(player_info, dict):
            continue

        for pid, info in player_info.items():
            if isinstance(pid, str) and isinstance(info, dict):
                players[pid] = info

    return players


def collect_player_refs(
    entries: list[dict[str, Any]],
) -> dict[int, set[str]]:
    refs: dict[int, set[str]] = defaultdict(set)

    for entry in entries:
        ud = entry.get("ud")
        if not isinstance(ud, dict):
            continue

        members = ud.get("members")
        if not isinstance(members, list):
            continue

        fallback_hostnum = entry.get("hostnum")

        for pid in members:
            if not isinstance(pid, str):
                continue

            hostnum: Any = None
            member_meta = ud.get(pid)
            if isinstance(member_meta, dict):
                hostnum = member_meta.get("hostnum")

            if not isinstance(hostnum, int):
                hostnum = fallback_hostnum

            if isinstance(hostnum, int):
                refs[hostnum].add(pid)

    return refs


def get_base(info: Any) -> dict[str, Any]:
    if not isinstance(info, dict):
        return {}
    base = info.get("base")
    return base if isinstance(base, dict) else {}


def enrich_entries(
    entries: list[dict[str, Any]],
    players: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for rank_index, entry in enumerate(entries, start=1):
        ud = entry.get("ud")
        ud = ud if isinstance(ud, dict) else {}

        members = ud.get("members")
        members = members if isinstance(members, list) else []

        leader_id = ud.get("leader_id")
        score = entry.get("score")

        member_rows: list[dict[str, Any]] = []
        for pid in members:
            if not isinstance(pid, str):
                continue

            info = players.get(pid, {})
            base = get_base(info)
            member_meta = ud.get(pid)
            hostnum = (
                member_meta.get("hostnum")
                if isinstance(member_meta, dict)
                else None
            )

            member_rows.append(
                {
                    "pid": pid,
                    "hostnum": hostnum,
                    "nickname": base.get("nickname"),
                    "number_id": base.get("number_id"),
                    "school": base.get("school"),
                    "level": base.get("level"),
                    "is_leader": pid == leader_id,
                    "player_info": info,
                }
            )

        leader = next(
            (
                member
                for member in member_rows
                if member["is_leader"]
            ),
            None,
        )

        enriched.append(
            {
                "rank": rank_index,
                "score": score,
                "duration": format_duration(score),
                "team_pid": entry.get("pid"),
                "hostnum": entry.get("hostnum"),
                "leader_id": leader_id,
                "leader_nickname": (
                    leader.get("nickname")
                    if isinstance(leader, dict)
                    else None
                ),
                "members": member_rows,
                "submitted_at": ud.get("ts"),
                "spaceids": ud.get("spaceids"),
                "raw": entry,
            }
        )

    return enriched


def write_rank_csv(
    path: Path,
    entries: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        fieldnames = [
            "rank",
            "score",
            "duration",
            "hostnum",
            "leader_id",
            "leader_nickname",
            "member_pids",
            "member_nicknames",
            "member_number_ids",
            "submitted_at",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for entry in entries:
            members = entry.get("members", [])
            writer.writerow(
                {
                    "rank": entry.get("rank"),
                    "score": entry.get("score"),
                    "duration": entry.get("duration"),
                    "hostnum": entry.get("hostnum"),
                    "leader_id": entry.get("leader_id"),
                    "leader_nickname": entry.get(
                        "leader_nickname"
                    ),
                    "member_pids": " | ".join(
                        str(member.get("pid", ""))
                        for member in members
                    ),
                    "member_nicknames": " | ".join(
                        str(member.get("nickname") or "")
                        for member in members
                    ),
                    "member_number_ids": " | ".join(
                        str(member.get("number_id") or "")
                        for member in members
                    ),
                    "submitted_at": entry.get("submitted_at"),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch complete public YYSL leaderboard pages and "
            "resolve all team member names."
        )
    )
    parser.add_argument(
        "--rank",
        action="append",
        dest="ranks",
        help=(
            "Leaderboard name. Repeat for multiple leaderboards. "
            f"Defaults: {', '.join(DEFAULT_RANKS)}"
        ),
    )
    parser.add_argument(
        "--pid",
        default=DEFAULT_PID,
        help="Internal player PID used by the public rank request.",
    )
    parser.add_argument(
        "--hostnum",
        type=int,
        default=DEFAULT_HOSTNUM,
        help="hostnum used by the captured public rank request.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "Desktop" / "yysls-ranks",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Delay between requests in seconds.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Maximum pages per leaderboard; 0 means all pages.",
    )
    parser.add_argument(
        "--player-batch-size",
        type=int,
        default=40,
        help="Players per get_players_info request.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ranks = args.ranks or DEFAULT_RANKS
    max_pages = args.max_pages if args.max_pages > 0 else None

    options = FetchOptions(
        delay_seconds=max(args.delay, 0.2),
        max_pages=max_pages,
        player_batch_size=max(1, args.player_batch_size),
        retries=max(1, args.retries),
    )

    run_dir = args.output_dir / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    run_summary: dict[str, Any] = {
        "fetched_at": time.time(),
        "pid": args.pid,
        "hostnum": args.hostnum,
        "ranks": {},
    }

    with YyslsClient(
        pid=args.pid,
        hostnum=args.hostnum,
        options=options,
    ) as client:
        for rank_name in ranks:
            print(f"\n=== {rank_name} ===")
            rank_dir = run_dir / rank_name
            raw_pages_dir = rank_dir / "raw-pages"

            entries, metadata = client.fetch_all_rank_pages(
                rank_name,
                raw_pages_dir,
            )

            print(f"  Collected {len(entries)} rank entries")

            players = merge_player_info_from_rank(entries)
            refs = collect_player_refs(entries)

            referenced_count = sum(
                len(pids) for pids in refs.values()
            )
            print(
                f"  Referenced players: {referenced_count}; "
                f"already embedded: {len(players)}"
            )

            fetched_players = client.fetch_players_info(refs)
            players.update(fetched_players)

            enriched = enrich_entries(entries, players)

            write_json(
                rank_dir / "players.json",
                players,
            )
            write_json(
                rank_dir / "rank.json",
                {
                    "metadata": metadata,
                    "entries": enriched,
                },
            )
            write_rank_csv(
                rank_dir / "rank.csv",
                enriched,
            )

            run_summary["ranks"][rank_name] = {
                **metadata,
                "entries_collected": len(entries),
                "players_resolved": len(players),
                "output_directory": str(rank_dir),
            }

            print(
                f"  Saved JSON and CSV to: {rank_dir}"
            )

            time.sleep(options.delay_seconds)

    write_json(run_dir / "summary.json", run_summary)
    print(f"\nAll outputs saved to: {run_dir}")


if __name__ == "__main__":
    main()
