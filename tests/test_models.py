import unittest

from src.models import (
    Period,
    RankBoard,
    aggregate_entries,
    compact_duration,
    format_duration_seconds,
    format_snapshot_time,
    lookup_duration_rank,
    parse_entries,
    parse_query_duration,
    precise_duration,
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

    def test_aggregation_keeps_a_large_same_second_in_one_segment(self):
        values = [
            {
                "rank": rank,
                "teamName": f"队伍{rank}",
                "durationStr": f"4:44.{(rank - 21) * 17:03d}",
                "snapshotTime": "20260723130000",
            }
            for rank in range(21, 71)
        ]

        aggregates = aggregate_entries(parse_entries(values))

        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0].rank_label, "21-70")
        self.assertEqual(aggregates[0].duration_label, "4:44")
        self.assertEqual(aggregates[0].team_count, 50)

    def test_aggregation_closes_after_whole_second_pushes_count_over_twenty(self):
        second_counts = (
            ("7:35", 7),
            ("7:36", 7),
            ("7:37", 8),
            ("7:38", 7),
            ("7:39", 7),
            ("7:40", 8),
        )
        values = []
        rank = 21
        for second, count in second_counts:
            for millisecond in range(count):
                values.append(
                    {
                        "rank": rank,
                        "teamName": f"队伍{rank}",
                        "durationStr": f"{second}.{millisecond:03d}",
                        "snapshotTime": "20260723130000",
                    }
                )
                rank += 1

        aggregates = aggregate_entries(parse_entries(values))

        self.assertEqual(len(aggregates), 2)
        self.assertEqual(aggregates[0].rank_label, "21-42")
        self.assertEqual(aggregates[0].duration_label, "7:35-7:37")
        self.assertEqual(aggregates[0].team_count, 22)
        self.assertEqual(aggregates[1].rank_label, "43-64")
        self.assertEqual(aggregates[1].duration_label, "7:38-7:40")
        self.assertEqual(aggregates[1].team_count, 22)

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

    def test_board_collapses_tail_slower_than_one_point_five_times_first(self):
        values = [
            {
                "rank": 1,
                "teamName": "第一名",
                "durationStr": "4:00.500",
                "snapshotTime": "20260723130000",
            }
        ]
        values.extend(
            {
                "rank": rank,
                "teamName": f"队伍{rank}",
                "durationStr": f"5:00.{rank:03d}",
                "snapshotTime": "20260723130000",
            }
            for rank in range(2, 21)
        )
        for rank, duration in enumerate(
            ("5:57.000", "5:58.000", "5:59.000", "6:00.000", "6:00.900"),
            start=21,
        ):
            values.append(
                {
                    "rank": rank,
                    "teamName": f"队伍{rank}",
                    "durationStr": duration,
                    "snapshotTime": "20260723130000",
                }
            )
        values.extend(
            {
                "rank": rank,
                "teamName": f"队伍{rank}",
                "durationStr": f"6:{rank - 25:02d}.000",
                "snapshotTime": "20260723130000",
            }
            for rank in range(26, 41)
        )
        board = RankBoard(
            period=Period.from_api(period(1, 1, 1, 1)),
            entries=parse_entries(values),
        )

        aggregates = board.aggregate_tail()

        self.assertEqual(len(aggregates), 2)
        self.assertEqual(aggregates[0].rank_label, "21-25")
        self.assertEqual(aggregates[0].duration_label, "5:57-6:00")
        self.assertEqual(aggregates[1].rank_label, "26-40")
        self.assertEqual(aggregates[1].duration_label, "6:01-6:15")
        self.assertEqual(aggregates[1].team_count, 15)

    def test_compacts_duration(self):
        self.assertEqual(compact_duration("7分11秒"), "7:11")

    def test_preserves_milliseconds_for_precise_duration(self):
        self.assertEqual(precise_duration("7:11.042"), "7:11.042")
        self.assertEqual(precise_duration("1:03:22.398"), "1:03:22.398")
        self.assertEqual(precise_duration("7分11秒"), "7:11")

    def test_parses_query_duration(self):
        self.assertEqual(parse_query_duration("7:11"), 431)
        self.assertEqual(parse_query_duration("7：11"), 431)
        self.assertEqual(format_duration_seconds(431), "7:11")
        with self.assertRaisesRegex(ValueError, "分:秒"):
            parse_query_duration("7:99")

    def test_finds_exact_rank_range_for_same_second(self):
        values = [
            {
                "rank": rank,
                "teamName": f"队伍{rank}",
                "durationStr": duration,
                "snapshotTime": "20260723130000",
            }
            for rank, duration in (
                (1, "7:10.900"),
                (2, "7:11.001"),
                (3, "7:11.800"),
                (4, "7:12.100"),
            )
        ]

        position = lookup_duration_rank(parse_entries(values), 431)

        self.assertTrue(position.exact)
        self.assertEqual(position.rank_label, "2-3")
        self.assertEqual(position.team_count, 2)

    def test_projects_rank_when_second_has_no_entry(self):
        values = [
            {
                "rank": rank,
                "teamName": f"队伍{rank}",
                "durationStr": duration,
                "snapshotTime": "20260723130000",
            }
            for rank, duration in (
                (1, "7:10.900"),
                (2, "7:12.100"),
                (3, "7:13.100"),
            )
        ]

        position = lookup_duration_rank(parse_entries(values), 431)

        self.assertFalse(position.exact)
        self.assertEqual(position.rank_label, "2")


if __name__ == "__main__":
    unittest.main()
