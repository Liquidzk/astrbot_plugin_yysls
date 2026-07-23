import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from src.api import RankService


def snapshot_payload() -> dict:
    boards = []
    for dungeon_type, period_type in ((1, 1), (1, 2), (2, 1), (2, 2)):
        boards.append(
            {
                "period": {
                    "id": dungeon_type * 10 + period_type,
                    "dungeonId": dungeon_type,
                    "dungeonName": "测试副本",
                    "dungeonType": dungeon_type,
                    "periodName": "测试副本 第2期",
                    "periodType": period_type,
                    "periodOrder": 2,
                    "seasonId": 0,
                    "startTime": "-",
                    "endTime": "-",
                },
                "entries": [
                    {
                        "rank": 1,
                        "teamName": "测试队伍",
                        "durationStr": "7:11.123",
                        "snapshotTime": "20260723220000",
                    }
                ],
            }
        )
    return {
        "schemaVersion": 1,
        "updatedAt": "2026-07-23 22:00",
        "boards": boards,
    }


class LocalSnapshotTests(unittest.TestCase):
    def test_loads_fresh_local_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "current-ranks.json"
            path.write_text(
                json.dumps(snapshot_payload(), ensure_ascii=False),
                encoding="utf-8",
            )

            snapshot = RankService(snapshot_path=path)._load_local_snapshot()

            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot.source, "网易公开排行榜")
            self.assertEqual(len(snapshot.boards), 4)
            self.assertEqual(snapshot.boards[0].entries[0].team_name, "测试队伍")

    def test_rejects_stale_snapshot_unless_allowed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "current-ranks.json"
            path.write_text(
                json.dumps(snapshot_payload()),
                encoding="utf-8",
            )
            old_time = time.time() - 3600
            os.utime(path, (old_time, old_time))
            service = RankService(
                snapshot_path=path,
                max_snapshot_age_seconds=60,
            )

            self.assertIsNone(service._load_local_snapshot())
            self.assertIsNotNone(
                service._load_local_snapshot(allow_stale=True)
            )


if __name__ == "__main__":
    unittest.main()
