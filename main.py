import os
import tempfile

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .src.api import RankApiError, RankService
from .src.render import RankRenderer


TEAM_SIZE_TYPES = {
    "十人": 1,
    "10人": 1,
    "十": 1,
    "10": 1,
    "五人": 2,
    "5人": 2,
    "五": 2,
    "5": 2,
}
DIFFICULTY_TYPES = {
    "普通": 1,
    "普通榜": 1,
    "挑战": 2,
    "挑战榜": 2,
}


@register(
    "astrbot_plugin_yysls",
    "Liquidzk",
    "燕云十六声当前活动周期四榜图片",
    "0.5.0",
    "https://github.com/Liquidzk/astrbot_plugin_yysls",
)
class YanyunRankPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.rank_service = RankService()
        self.renderer = RankRenderer()

    @filter.command("燕云")
    async def yanyun_help(self, event: AstrMessageEvent):
        """查看燕云插件帮助。"""
        yield event.plain_result(
            "【燕云十六声】\n"
            "/排行榜 - 当前活动周期四榜总图\n"
            "/排行榜 五人 - 五人普通、挑战双榜\n"
            "/排行榜 十人 - 十人普通、挑战双榜\n"
            "/排行榜 五人 普通|挑战 - 五人单榜\n"
            "/排行榜 十人 普通|挑战 - 十人单榜\n\n"
            "前 20 名显示队伍，之后分段聚合。"
        )

    @filter.command("排行榜")
    async def latest_rank(
        self,
        event: AstrMessageEvent,
        team_size: str = "",
        difficulty: str = "",
    ):
        """生成当前活动周期的四榜图片。"""
        image_path = ""
        try:
            snapshot = await self.rank_service.get_latest()
            selected_board = None
            selected_pair = None
            if team_size:
                team_size_type = TEAM_SIZE_TYPES.get(team_size.strip())
                difficulty_text = difficulty.strip()
                difficulty_type = (
                    DIFFICULTY_TYPES.get(difficulty_text)
                    if difficulty_text
                    else None
                )
                if team_size_type is None or (
                    difficulty_text and difficulty_type is None
                ):
                    yield event.plain_result(
                        "参数格式：/排行榜 [五人|十人] [普通|挑战]\n"
                        "示例：/排行榜 五人 挑战"
                    )
                    return
                matching_boards = tuple(
                    sorted(
                        (
                            item
                            for item in snapshot.boards
                            if item.period.dungeon_type == team_size_type
                        ),
                        key=lambda item: item.period.period_type,
                    )
                )
                if difficulty_type is None:
                    if len(matching_boards) != 2:
                        yield event.plain_result("当前活动周期的双榜数据不完整。")
                        return
                    selected_pair = matching_boards
                else:
                    selected_board = next(
                        (
                            item
                            for item in matching_boards
                            if item.period.period_type == difficulty_type
                        ),
                        None,
                    )
                if difficulty_type is not None and selected_board is None:
                    yield event.plain_result("当前活动周期没有对应榜单。")
                    return
            elif difficulty.strip():
                yield event.plain_result(
                    "请先指定五人或十人。\n"
                    "示例：/排行榜 五人 挑战"
                )
                return

            handle, image_path = tempfile.mkstemp(
                prefix="yysls_rank_",
                suffix=".png",
            )
            os.close(handle)
            if selected_board:
                self.renderer.render_detail(
                    selected_board,
                    snapshot.updated_at,
                    image_path,
                )
            elif selected_pair:
                self.renderer.render_pair(
                    selected_pair,
                    snapshot.updated_at,
                    image_path,
                )
            else:
                self.renderer.render_overview(snapshot, image_path)
            logger.info(
                "燕云排行榜使用数据快照: %s (%s)",
                snapshot.updated_at,
                snapshot.source,
            )
            event.track_temporary_local_file(image_path)
            yield event.image_result(image_path)
        except RankApiError as exc:
            logger.warning("燕云排行榜数据获取失败: %s", exc)
            yield event.plain_result(f"排行榜获取失败：{exc}")
        except Exception:
            logger.exception("燕云排行榜生成失败")
            if image_path:
                try:
                    os.unlink(image_path)
                except OSError:
                    pass
            yield event.plain_result("排行榜生成失败，请稍后重试。")
