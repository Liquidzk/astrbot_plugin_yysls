import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.models import Period, RankBoard, RankingEntry, RankSnapshot
from src.render import RankRenderer


class RenderTests(unittest.TestCase):
    def setUp(self):
        boards = []
        for board_index in range(4):
            period = Period(
                id=board_index + 1,
                dungeon_id=board_index // 2 + 1,
                dungeon_name=f"测试副本{board_index // 2 + 1}",
                dungeon_type=board_index // 2 + 1,
                period_name=f"测试副本 {board_index + 1} 挑战第2期",
                period_type=board_index % 2 + 1,
                period_order=2,
                season_id=3,
                start_time="2026-07-10 10:00:00",
                end_time="2026-07-24 00:00:00",
            )
            entries = tuple(
                RankingEntry(
                    rank=rank,
                    team_name=f"测试队伍{rank}",
                    duration=(
                        f"{rank + 3}分{rank}秒"
                        if rank <= 20
                        else "8分11秒"
                    ),
                    snapshot_time="20260723130000",
                )
                for rank in range(1, 31)
            )
            boards.append(RankBoard(period=period, entries=entries))

        self.snapshot = RankSnapshot(
            boards=tuple(boards),
            updated_at="2026-07-23 13:00",
        )

    def test_renders_nonblank_four_board_overview(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "rank.png"
            RankRenderer().render_overview(self.snapshot, str(output))
            with Image.open(output) as image:
                self.assertEqual(image.width, 2320)
                self.assertGreater(image.height, 1000)
                self.assertGreater(len(image.getcolors(maxcolors=1_000_000)), 10)

    def test_renders_nonblank_detail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "detail.png"
            RankRenderer().render_detail(
                self.snapshot.boards[0],
                self.snapshot.updated_at,
                str(output),
            )
            with Image.open(output) as image:
                self.assertEqual(image.width, 820)
                self.assertGreater(image.height, 1000)
                self.assertGreater(len(image.getcolors(maxcolors=1_000_000)), 10)

    def test_renders_nonblank_team_size_pair(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "pair.png"
            RankRenderer().render_pair(
                self.snapshot.boards[:2],
                self.snapshot.updated_at,
                str(output),
            )
            with Image.open(output) as image:
                self.assertEqual(image.width, 1180)
                self.assertGreater(image.height, 1000)
                self.assertGreater(len(image.getcolors(maxcolors=1_000_000)), 10)


if __name__ == "__main__":
    unittest.main()
