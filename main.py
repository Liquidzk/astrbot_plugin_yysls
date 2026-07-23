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
    "0.3.1",
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
            "/排行榜 五人 [普通|挑战] - 五人详细榜\n"
            "/排行榜 十人 [普通|挑战] - 十人详细榜\n\n"
            "未写难度时默认为普通。前 20 名显示队伍，之后分段聚合。"
        )

    @filter.command("排行榜")
    async def latest_rank(
        self,
        event: AstrMessageEvent,
        team_size: str = "",
        difficulty: str = "普通",
    ):
        """生成当前活动周期的四榜图片。"""
        image_path = ""
        try:
            snapshot = await self.rank_service.get_latest()
            board = None
            if team_size:
                team_size_type = TEAM_SIZE_TYPES.get(team_size.strip())
                difficulty_type = DIFFICULTY_TYPES.get(difficulty.strip())
                if team_size_type is None or difficulty_type is None:
                    yield event.plain_result(
                        "参数格式：/排行榜 [五人|十人] [普通|挑战]\n"
                        "示例：/排行榜 五人 挑战"
                    )
                    return
                board = next(
                    (
                        item
                        for item in snapshot.boards
                        if item.period.dungeon_type == team_size_type
                        and item.period.period_type == difficulty_type
                    ),
                    None,
                )
                if board is None:
                    yield event.plain_result("当前活动周期没有对应榜单。")
                    return

            handle, image_path = tempfile.mkstemp(
                prefix="yysls_rank_",
                suffix=".png",
            )
            os.close(handle)
            if board:
                self.renderer.render_detail(
                    board,
                    snapshot.updated_at,
                    image_path,
                )
            else:
                self.renderer.render_overview(snapshot, image_path)
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
