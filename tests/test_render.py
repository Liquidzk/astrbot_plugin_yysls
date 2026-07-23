import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.models import Period, RankBoard, RankingEntry, RankSnapshot
from src.render import RankRenderer


class RenderTests(unittest.TestCase):
    def test_renders_nonblank_four_board_image(self):
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
                    duration=f"{rank + 3}分{rank}秒",
                    snapshot_time="20260723130000",
                )
                for rank in range(1, 11)
            )
            boards.append(RankBoard(period=period, entries=entries))

        snapshot = RankSnapshot(
            boards=tuple(boards),
            updated_at="2026-07-23 13:00",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "rank.png"
            RankRenderer().render(snapshot, str(output))
            with Image.open(output) as image:
                self.assertEqual(image.size, (1440, 1680))
                self.assertGreater(len(image.getcolors(maxcolors=1_000_000)), 10)


if __name__ == "__main__":
    unittest.main()

