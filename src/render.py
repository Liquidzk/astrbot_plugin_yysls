from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import RankBoard, RankSnapshot


class RankRenderer:
    WIDTH = 1440
    HEIGHT = 1680
    CARD_WIDTH = 660
    CARD_HEIGHT = 640

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
        if len(snapshot.boards) != 4:
            raise ValueError("四榜图片必须包含 4 个榜单")

        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.BACKGROUND)
        draw = ImageDraw.Draw(image)
        self._draw_background(draw)
        self._draw_header(draw, snapshot)

        positions = ((48, 244), (732, 244), (48, 908), (732, 908))
        for index, (board, position) in enumerate(zip(snapshot.boards, positions)):
            self._draw_board(draw, board, position, self.ACCENTS[index])

        self._draw_footer(draw)
        image.save(output_path, format="PNG", optimize=True)

    def _draw_background(self, draw: ImageDraw.ImageDraw) -> None:
        draw.rectangle((0, 0, self.WIDTH, 10), fill=self.ACCENTS[0])
        draw.rectangle((self.WIDTH // 2, 0, self.WIDTH, 10), fill=self.ACCENTS[1])
        for y in range(96, self.HEIGHT, 160):
            draw.line((0, y, self.WIDTH, y - 72), fill="#142023", width=1)

    def _draw_header(
        self,
        draw: ImageDraw.ImageDraw,
        snapshot: RankSnapshot,
    ) -> None:
        draw.text(
            (48, 48),
            "燕云赛季四榜",
            font=self.font(58, bold=True),
            fill=self.TEXT,
        )
        draw.text(
            (50, 126),
            "当前活动周期 · 实时团队排名 TOP 10",
            font=self.font(26),
            fill=self.MUTED,
        )
        updated_text = f"数据更新时间  {snapshot.updated_at}"
        width = draw.textlength(updated_text, font=self.font(24))
        draw.text(
            (self.WIDTH - 48 - width, 130),
            updated_text,
            font=self.font(24),
            fill=self.MUTED,
        )
        draw.line((48, 205, self.WIDTH - 48, 205), fill=self.BORDER, width=2)

    def _draw_board(
        self,
        draw: ImageDraw.ImageDraw,
        board: RankBoard,
        position: tuple[int, int],
        accent: str,
    ) -> None:
        x, y = position
        right = x + self.CARD_WIDTH
        bottom = y + self.CARD_HEIGHT
        draw.rounded_rectangle(
            (x, y, right, bottom),
            radius=8,
            fill=self.SURFACE,
            outline=self.BORDER,
            width=2,
        )
        draw.rectangle((x, y, x + 8, bottom), fill=accent)

        title = self._ellipsize(
            draw,
            board.period.period_name,
            self.font(30, bold=True),
            self.CARD_WIDTH - 64,
        )
        draw.text(
            (x + 30, y + 24),
            title,
            font=self.font(30, bold=True),
            fill=self.TEXT,
        )
        detail = (
            f"{board.period.difficulty_name}榜  ·  "
            f"{len(board.entries)} 条  ·  截止 {board.period.end_time[:16]}"
        )
        draw.text(
            (x + 31, y + 70),
            detail,
            font=self.font(20),
            fill=accent,
        )

        header_y = y + 112
        draw.rectangle(
            (x + 16, header_y, right - 16, header_y + 42),
            fill=self.SURFACE_ALT,
        )
        draw.text(
            (x + 34, header_y + 8),
            "名次",
            font=self.font(19, bold=True),
            fill=self.MUTED,
        )
        draw.text(
            (x + 113, header_y + 8),
            "队伍",
            font=self.font(19, bold=True),
            fill=self.MUTED,
        )
        draw.text(
            (right - 126, header_y + 8),
            "用时",
            font=self.font(19, bold=True),
            fill=self.MUTED,
        )

        row_top = header_y + 46
        for row_index, entry in enumerate(board.entries):
            top = row_top + row_index * 46
            if row_index % 2:
                draw.rectangle(
                    (x + 16, top, right - 16, top + 44),
                    fill="#1A2528",
                )
            if row_index:
                draw.line(
                    (x + 30, top, right - 30, top),
                    fill="#273437",
                    width=1,
                )

            rank_fill = accent if entry.rank <= 3 else self.MUTED
            rank_text = str(entry.rank)
            rank_font = self.font(21, bold=entry.rank <= 3)
            rank_width = draw.textlength(rank_text, font=rank_font)
            draw.text(
                (x + 60 - rank_width / 2, top + 9),
                rank_text,
                font=rank_font,
                fill=rank_fill,
            )

            team_font = self.font(22, bold=entry.rank <= 3)
            team_name = self._ellipsize(
                draw,
                entry.team_name,
                team_font,
                330,
            )
            draw.text(
                (x + 113, top + 7),
                team_name,
                font=team_font,
                fill=self.TEXT,
            )

            duration_font = self.font(21)
            duration_width = draw.textlength(entry.duration, font=duration_font)
            draw.text(
                (right - 30 - duration_width, top + 8),
                entry.duration,
                font=duration_font,
                fill=self.TEXT,
            )

    def _draw_footer(self, draw: ImageDraw.ImageDraw) -> None:
        draw.line(
            (48, 1588, self.WIDTH - 48, 1588),
            fill=self.BORDER,
            width=2,
        )
        draw.text(
            (48, 1615),
            "数据来源：yysls.rubysiu.cn  ·  排名以数据源实时结果为准",
            font=self.font(22),
            fill=self.MUTED,
        )
        marker = "ASTRBOT · YANYUN"
        marker_width = draw.textlength(marker, font=self.font(18, bold=True))
        draw.text(
            (self.WIDTH - 48 - marker_width, 1618),
            marker,
            font=self.font(18, bold=True),
            fill=self.ACCENTS[0],
        )

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

