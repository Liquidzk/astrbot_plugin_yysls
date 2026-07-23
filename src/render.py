from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import (
    RankAggregate,
    RankBoard,
    RankingEntry,
    RankSnapshot,
    compact_duration,
)


class RankRenderer:
    TOP_LIMIT = 20
    ROW_HEIGHT = 40
    OVERVIEW_WIDTH = 2760
    DETAIL_WIDTH = 1120

    BACKGROUND = "#101719"
    SURFACE = "#182225"
    SURFACE_ALT = "#1D292C"
    BORDER = "#334246"
    TEXT = "#F2F4F1"
    MUTED = "#AAB7B5"
    ACCENTS = ("#4EB5A8", "#E06C5F", "#D9B45B", "#70A9C4")

    def __init__(self):
        self.font_regular = self._font_path(
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        )
        self.font_bold = self._font_path(
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        )

    @staticmethod
    def _font_path(*candidates: str) -> str:
        for candidate in candidates:
            if Path(candidate).exists():
                return candidate
        raise RuntimeError("未找到可用的中文字体")

    def font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(self.font_bold if bold else self.font_regular, size)

    def render(self, snapshot: RankSnapshot, output_path: str) -> None:
        self.render_overview(snapshot, output_path)

    def render_overview(self, snapshot: RankSnapshot, output_path: str) -> None:
        if len(snapshot.boards) != 4:
            raise ValueError("四榜总图必须包含 4 个榜单")

        row_counts = [self._row_count(board) for board in snapshot.boards]
        board_top = 232
        board_header_height = 156
        board_height = board_header_height + max(row_counts) * self.ROW_HEIGHT + 24
        footer_top = board_top + board_height + 34
        height = footer_top + 86

        image = Image.new("RGB", (self.OVERVIEW_WIDTH, height), self.BACKGROUND)
        draw = ImageDraw.Draw(image)
        self._draw_background(draw, self.OVERVIEW_WIDTH, height)
        self._draw_page_header(
            draw,
            width=self.OVERVIEW_WIDTH,
            title="燕云赛季总榜",
            subtitle="当前活动周期 · 前 20 名队伍 + 尾部同用时聚合",
            updated_at=snapshot.updated_at,
        )

        margin = 48
        gap = 20
        board_width = (
            self.OVERVIEW_WIDTH - margin * 2 - gap * 3
        ) // 4
        for index, board in enumerate(snapshot.boards):
            x = margin + index * (board_width + gap)
            self._draw_board(
                draw,
                board=board,
                box=(x, board_top, board_width, board_height),
                accent=self.ACCENTS[index],
                compact=True,
            )

        self._draw_footer(draw, self.OVERVIEW_WIDTH, footer_top)
        image.save(output_path, format="PNG", optimize=True)

    def render_detail(
        self,
        board: RankBoard,
        updated_at: str,
        output_path: str,
    ) -> None:
        board_top = 232
        board_header_height = 156
        board_height = (
            board_header_height
            + self._row_count(board) * self.ROW_HEIGHT
            + 24
        )
        footer_top = board_top + board_height + 34
        height = footer_top + 86

        image = Image.new("RGB", (self.DETAIL_WIDTH, height), self.BACKGROUND)
        draw = ImageDraw.Draw(image)
        self._draw_background(draw, self.DETAIL_WIDTH, height)
        title = (
            f"燕云 · {board.period.team_size_name}"
            f"{board.period.difficulty_name}榜"
        )
        self._draw_page_header(
            draw,
            width=self.DETAIL_WIDTH,
            title=title,
            subtitle=board.period.period_name,
            updated_at=updated_at,
        )
        self._draw_board(
            draw,
            board=board,
            box=(48, board_top, self.DETAIL_WIDTH - 96, board_height),
            accent=self._accent_for(board),
            compact=False,
        )
        self._draw_footer(draw, self.DETAIL_WIDTH, footer_top)
        image.save(output_path, format="PNG", optimize=True)

    def _row_count(self, board: RankBoard) -> int:
        return (
            len(board.top_entries(self.TOP_LIMIT))
            + len(board.aggregate_tail(self.TOP_LIMIT))
            + 1
        )

    def _draw_background(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
    ) -> None:
        half = width // 2
        draw.rectangle((0, 0, half, 10), fill=self.ACCENTS[0])
        draw.rectangle((half, 0, width, 10), fill=self.ACCENTS[1])
        for y in range(96, height, 180):
            draw.line((0, y, width, y - 72), fill="#142023", width=1)

    def _draw_page_header(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        title: str,
        subtitle: str,
        updated_at: str,
    ) -> None:
        draw.text(
            (48, 42),
            title,
            font=self.font(54, bold=True),
            fill=self.TEXT,
        )
        draw.text(
            (50, 119),
            subtitle,
            font=self.font(25),
            fill=self.MUTED,
        )
        updated_text = f"数据更新时间  {updated_at}"
        updated_font = self.font(22)
        updated_width = draw.textlength(updated_text, font=updated_font)
        draw.text(
            (width - 48 - updated_width, 126),
            updated_text,
            font=updated_font,
            fill=self.MUTED,
        )
        draw.line((48, 198, width - 48, 198), fill=self.BORDER, width=2)

    def _draw_board(
        self,
        draw: ImageDraw.ImageDraw,
        board: RankBoard,
        box: tuple[int, int, int, int],
        accent: str,
        compact: bool,
    ) -> None:
        x, y, width, height = box
        right = x + width
        bottom = y + height
        draw.rounded_rectangle(
            (x, y, right, bottom),
            radius=8,
            fill=self.SURFACE,
            outline=self.BORDER,
            width=2,
        )
        draw.rectangle((x, y, x + 8, bottom), fill=accent)

        title_font = self.font(27 if compact else 31, bold=True)
        title = self._ellipsize(
            draw,
            board.period.period_name,
            title_font,
            width - 58,
        )
        draw.text((x + 28, y + 20), title, font=title_font, fill=self.TEXT)

        detail = (
            f"{board.period.team_size_name} · {board.period.difficulty_name}榜"
            f" · 共 {len(board.entries)} 条"
        )
        draw.text(
            (x + 29, y + 63),
            detail,
            font=self.font(19 if compact else 21),
            fill=accent,
        )

        table_top = y + 104
        table_left = x + 16
        table_right = right - 16
        rank_width = 112 if compact else 145
        duration_width = 118 if compact else 155
        team_left = table_left + rank_width
        duration_left = table_right - duration_width

        draw.rectangle(
            (table_left, table_top, table_right, table_top + 42),
            fill=self.SURFACE_ALT,
        )
        header_font = self.font(18 if compact else 20, bold=True)
        draw.text(
            (table_left + 18, table_top + 9),
            "名次",
            font=header_font,
            fill=self.MUTED,
        )
        draw.text(
            (team_left + 6, table_top + 9),
            "队伍",
            font=header_font,
            fill=self.MUTED,
        )
        draw.text(
            (duration_left + 12, table_top + 9),
            "用时",
            font=header_font,
            fill=self.MUTED,
        )

        row_top = y + 150
        row_index = 0
        for entry in board.top_entries(self.TOP_LIMIT):
            self._draw_entry_row(
                draw,
                entry=entry,
                row_index=row_index,
                top=row_top + row_index * self.ROW_HEIGHT,
                table_left=table_left,
                table_right=table_right,
                team_left=team_left,
                duration_left=duration_left,
                accent=accent,
                compact=compact,
            )
            row_index += 1

        separator_top = row_top + row_index * self.ROW_HEIGHT
        draw.rectangle(
            (
                table_left,
                separator_top,
                table_right,
                separator_top + self.ROW_HEIGHT - 1,
            ),
            fill=self.SURFACE_ALT,
        )
        separator_text = "21名以后 · 连续相同用时聚合"
        draw.text(
            (table_left + 18, separator_top + 8),
            separator_text,
            font=self.font(18 if compact else 20, bold=True),
            fill=accent,
        )
        row_index += 1

        for aggregate in board.aggregate_tail(self.TOP_LIMIT):
            self._draw_aggregate_row(
                draw,
                aggregate=aggregate,
                row_index=row_index,
                top=row_top + row_index * self.ROW_HEIGHT,
                table_left=table_left,
                table_right=table_right,
                duration_left=duration_left,
                compact=compact,
            )
            row_index += 1

    def _draw_entry_row(
        self,
        draw: ImageDraw.ImageDraw,
        entry: RankingEntry,
        row_index: int,
        top: int,
        table_left: int,
        table_right: int,
        team_left: int,
        duration_left: int,
        accent: str,
        compact: bool,
    ) -> None:
        self._draw_row_base(
            draw,
            row_index,
            top,
            table_left,
            table_right,
        )
        text_font = self.font(20 if compact else 22)
        top_font = self.font(20 if compact else 22, bold=entry.rank <= 3)
        draw.text(
            (table_left + 20, top + 7),
            str(entry.rank),
            font=top_font,
            fill=accent if entry.rank <= 3 else self.MUTED,
        )

        team_width = duration_left - team_left - 12
        team_name = self._limit_team_name(
            draw,
            entry.team_name,
            top_font,
            team_width,
        )
        draw.text(
            (team_left + 6, top + 6),
            team_name,
            font=top_font,
            fill=self.TEXT,
        )
        draw.text(
            (duration_left + 12, top + 7),
            compact_duration(entry.duration),
            font=text_font,
            fill=self.TEXT,
        )

    def _draw_aggregate_row(
        self,
        draw: ImageDraw.ImageDraw,
        aggregate: RankAggregate,
        row_index: int,
        top: int,
        table_left: int,
        table_right: int,
        duration_left: int,
        compact: bool,
    ) -> None:
        self._draw_row_base(
            draw,
            row_index,
            top,
            table_left,
            table_right,
        )
        aggregate_font = self.font(19 if compact else 21)
        draw.text(
            (table_left + 20, top + 7),
            aggregate.rank_label,
            font=aggregate_font,
            fill=self.MUTED,
        )
        draw.text(
            (duration_left + 12, top + 7),
            compact_duration(aggregate.duration),
            font=aggregate_font,
            fill=self.MUTED,
        )

    def _draw_row_base(
        self,
        draw: ImageDraw.ImageDraw,
        row_index: int,
        top: int,
        table_left: int,
        table_right: int,
    ) -> None:
        if row_index % 2:
            draw.rectangle(
                (
                    table_left,
                    top,
                    table_right,
                    top + self.ROW_HEIGHT - 1,
                ),
                fill="#1A2528",
            )
        if row_index:
            draw.line(
                (table_left + 12, top, table_right - 12, top),
                fill="#273437",
                width=1,
            )

    def _draw_footer(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        top: int,
    ) -> None:
        draw.line((48, top, width - 48, top), fill=self.BORDER, width=2)
        draw.text(
            (48, top + 27),
            "数据来源：yysls.rubysiu.cn · 排名以数据源实时结果为准",
            font=self.font(21),
            fill=self.MUTED,
        )
        marker = "ASTRBOT · YANYUN"
        marker_font = self.font(18, bold=True)
        marker_width = draw.textlength(marker, font=marker_font)
        draw.text(
            (width - 48 - marker_width, top + 30),
            marker,
            font=marker_font,
            fill=self.ACCENTS[0],
        )

    def _limit_team_name(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: float,
    ) -> str:
        if len(text) > 12:
            text = text[:12] + "…"
        return self._ellipsize(draw, text, font, max_width)

    @staticmethod
    def _ellipsize(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: float,
    ) -> str:
        if draw.textlength(text, font=font) <= max_width:
            return text
        suffix = "…"
        while text and draw.textlength(text + suffix, font=font) > max_width:
            text = text[:-1]
        return text + suffix

    def _accent_for(self, board: RankBoard) -> str:
        index_by_type = {
            (1, 1): 0,
            (1, 2): 1,
            (2, 1): 2,
            (2, 2): 3,
        }
        return self.ACCENTS[
            index_by_type.get(
                (board.period.dungeon_type, board.period.period_type),
                0,
            )
        ]
