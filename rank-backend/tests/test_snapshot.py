import tempfile
import unittest
from pathlib import Path

from yysls_rank_tool.snapshot import (
    CURRENT_PHASE_TWO_BOARDS,
    convert_entries,
    write_snapshot_atomic,
)


class SnapshotTests(unittest.TestCase):
    def test_phase_two_rank_mapping(self):
        mapping = {
            (board.team_size_name, board.difficulty_name): board.rank_name
            for board in CURRENT_PHASE_TWO_BOARDS
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
