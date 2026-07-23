import unittest

from src.models import (
    aggregate_entries,
    compact_duration,
    format_snapshot_time,
    parse_entries,
    select_latest_four_periods,
)


def period(
    period_id: int,
    dungeon_id: int,
    dungeon_type: int,
    period_type: int,
    period_order: int = 2,
    season_id: int = 3,
) -> dict:
    return {
        "id": period_id,
        "dungeonId": dungeon_id,
        "dungeonName": f"副本{dungeon_id}",
        "dungeonType": dungeon_type,
        "periodName": f"副本{dungeon_id} 第{period_order}期",
        "periodType": period_type,
        "periodOrder": period_order,
        "seasonId": season_id,
        "startTime": "2026-07-10 10:00:00",
        "endTime": "2026-07-24 00:00:00",
    }


class ModelTests(unittest.TestCase):
    def test_selects_latest_four_and_stable_order(self):
        values = [
            period(20, 4, 2, 1),
            period(17, 3, 1, 2),
            period(23, 4, 2, 2),
            period(14, 3, 1, 1),
            period(4, 3, 1, 1, period_order=1),
        ]

        selected = select_latest_four_periods(values)

        self.assertEqual([item.id for item in selected], [14, 17, 20, 23])

    def test_rejects_non_four_active_boards(self):
        with self.assertRaisesRegex(ValueError, "预期为 4"):
            select_latest_four_periods([period(14, 3, 1, 1)])

    def test_entries_are_sorted_and_limited(self):
        values = [
            {
                "rank": rank,
                "teamName": f"队伍{rank}",
                "durationStr": f"{rank}分",
                "snapshotTime": "20260723130000",
            }
            for rank in range(12, 0, -1)
        ]

        entries = parse_entries(values, limit=10)

        self.assertEqual(len(entries), 10)
        self.assertEqual(entries[0].rank, 1)
        self.assertEqual(entries[-1].rank, 10)

    def test_formats_snapshot_time(self):
        self.assertEqual(
            format_snapshot_time("20260723130008"),
            "2026-07-23 13:00",
        )

    def test_normal_aggregation_waits_for_minimum_and_span(self):
        values = [
            {
                "rank": rank,
                "teamName": f"队伍{rank}",
                "durationStr": duration,
                "snapshotTime": "20260723130000",
            }
            for rank, duration in (
                (21, "7分11秒"),
                (22, "7分12秒"),
                (23, "7分13秒"),
                (24, "7分14秒"),
                (25, "7分15秒"),
            )
        ]

        aggregates = aggregate_entries(parse_entries(values))

        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0].rank_label, "21-25")
        self.assertEqual(aggregates[0].duration_label, "7:11-7:15")
        self.assertEqual(aggregates[0].team_count, 5)

    def test_aggregation_closes_after_current_second_reaches_twenty(self):
        values = [
            {
                "rank": rank,
                "teamName": f"队伍{rank}",
                "durationStr": "7分11秒" if rank <= 30 else "7分12秒",
                "snapshotTime": "20260723130000",
            }
            for rank in range(21, 41)
        ]

        aggregates = aggregate_entries(parse_entries(values))

        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0].rank_label, "21-40")
        self.assertEqual(aggregates[0].team_count, 20)

    def test_challenge_uses_six_second_span(self):
        values = [
            {
                "rank": rank,
                "teamName": f"队伍{rank}",
                "durationStr": duration,
                "snapshotTime": "20260723130000",
            }
            for rank, duration in (
                (21, "7分11秒"),
                (22, "7分12秒"),
                (23, "7分13秒"),
                (24, "7分14秒"),
                (25, "7分15秒"),
                (26, "7分17秒"),
            )
        ]

        aggregates = aggregate_entries(
            parse_entries(values),
            max_span_seconds=6,
        )

        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0].rank_label, "21-26")
        self.assertEqual(aggregates[0].duration_label, "7:11-7:17")

    def test_unclosed_tail_merges_into_previous_segment(self):
        values = [
            {
                "rank": rank,
                "teamName": f"队伍{rank}",
                "durationStr": duration,
                "snapshotTime": "20260723130000",
            }
            for rank, duration in (
                (21, "7分11秒"),
                (22, "7分12秒"),
                (23, "7分13秒"),
                (24, "7分14秒"),
                (25, "7分15秒"),
                (26, "7分16秒"),
                (27, "7分16秒"),
                (28, "7分16秒"),
                (29, "7分16秒"),
                (30, "7分16秒"),
            )
        ]

        aggregates = aggregate_entries(parse_entries(values))

        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0].rank_label, "21-30")
        self.assertEqual(aggregates[0].team_count, 10)

    def test_compacts_duration(self):
        self.assertEqual(compact_duration("7分11秒"), "7:11")


if __name__ == "__main__":
    unittest.main()
