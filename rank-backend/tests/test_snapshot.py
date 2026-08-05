import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from yysls_rank_tool.snapshot import (
    apply_due_scheduled_events,
    convert_entries,
    load_board_specs,
    write_snapshot_atomic,
)


class SnapshotTests(unittest.TestCase):
    def test_phase_two_rank_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ranks.json"
            path.write_text(
                json.dumps(
                    {
                        "periodOrder": 2,
                        "five": {
                            "dungeonName": "沧流走虺",
                            "normalRankId": 63,
                            "challengeRankId": 60,
                        },
                        "ten": {
                            "dungeonName": "风翎掠寒江",
                            "normalRankId": 62,
                            "challengeRankId": 59,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            boards = load_board_specs(path)

        mapping = {
            (board.team_size_name, board.difficulty_name): board.rank_name
            for board in boards
        }

        self.assertEqual(
            mapping,
            {
                ("十人", "普通"): "rank_team10_dungeon_62",
                ("十人", "挑战"): "rank_team10_dungeon_59",
                ("五人", "普通"): "rank_team_dungeon_63",
                ("五人", "挑战"): "rank_team_dungeon_60",
            },
        )
        self.assertEqual({board.period_order for board in boards}, {2})

    def test_applies_due_small_rollover_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ranks.json"
            path.write_text(
                json.dumps(
                    {
                        "periodOrder": 2,
                        "five": {
                            "dungeonName": "五人副本",
                            "normalRankId": 63,
                            "challengeRankId": 60,
                        },
                        "ten": {
                            "dungeonName": "十人副本",
                            "normalRankId": 62,
                            "challengeRankId": 59,
                        },
                        "scheduledEvents": [
                            {
                                "id": "small-rollover",
                                "at": "2026-07-24T06:00:00+08:00",
                                "action": "incrementPeriodAndRankIds",
                                "delta": 1,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            applied = apply_due_scheduled_events(
                path,
                now=datetime.fromisoformat("2026-07-24T06:00:00+08:00"),
            )
            applied_again = apply_due_scheduled_events(
                path,
                now=datetime.fromisoformat("2026-07-24T07:00:00+08:00"),
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(applied, ("small-rollover",))
            self.assertEqual(applied_again, ())
            self.assertEqual(payload["periodOrder"], 3)
            self.assertEqual(payload["five"]["normalRankId"], 64)
            self.assertEqual(payload["five"]["challengeRankId"], 61)
            self.assertEqual(payload["ten"]["normalRankId"], 63)
            self.assertEqual(payload["ten"]["challengeRankId"], 60)
            self.assertIn(
                "appliedAt",
                payload["scheduledEvents"][0],
            )

    def test_does_not_apply_future_rollover(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ranks.json"
            payload = {
                "periodOrder": 2,
                "five": {
                    "dungeonName": "五人副本",
                    "normalRankId": 63,
                    "challengeRankId": 60,
                },
                "ten": {
                    "dungeonName": "十人副本",
                    "normalRankId": 62,
                    "challengeRankId": 59,
                },
                "scheduledEvents": [
                    {
                        "id": "future-rollover",
                        "at": "2026-07-24T06:00:00+08:00",
                        "action": "incrementPeriodAndRankIds",
                    }
                ],
            }
            path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

            applied = apply_due_scheduled_events(
                path,
                now=datetime.fromisoformat("2026-07-24T05:59:59+08:00"),
            )

            self.assertEqual(applied, ())
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                payload,
            )

    def test_rejects_invalid_rank_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ranks.json"
            path.write_text(
                json.dumps(
                    {
                        "periodOrder": 3,
                        "five": {
                            "dungeonName": "五人副本",
                            "normalRankId": 0,
                            "challengeRankId": 70,
                        },
                        "ten": {
                            "dungeonName": "十人副本",
                            "normalRankId": 72,
                            "challengeRankId": 69,
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "必须是正整数"):
                load_board_specs(path)

    def test_converts_embedded_leader_and_duration(self):
        entries = [
            {
                "score": -468.124,
                "ud": {
                    "leader_id": "leader",
                    "members": ["leader"],
                },
                "player_info": {
                    "leader": {
                        "base": {
                            "nickname": "测试队长",
                        }
                    }
                },
            }
        ]

        converted = convert_entries(entries, "20260723220000")

        self.assertEqual(converted[0]["rank"], 1)
        self.assertEqual(converted[0]["teamName"], "测试队长")
        self.assertEqual(converted[0]["durationStr"], "7:48.124")

    def test_writes_snapshot_atomically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "current-ranks.json"

            write_snapshot_atomic(path, {"schemaVersion": 1})

            self.assertTrue(path.is_file())
            self.assertFalse(path.with_suffix(".json.tmp").exists())
            self.assertIn('"schemaVersion": 1', path.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
