import json
import tempfile
import unittest
from pathlib import Path

from yysls_rank_tool.snapshot import (
    convert_entries,
    default_config_path,
    load_board_specs,
    write_snapshot_atomic,
)


class SnapshotTests(unittest.TestCase):
    def test_phase_two_rank_mapping(self):
        boards = load_board_specs(default_config_path())
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
