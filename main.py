import os
import tempfile

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .src.api import RankApiError, RankService
from .src.render import RankRenderer


@register(
    "astrbot_plugin_yysls",
    "Liquidzk",
    "燕云十六声当前活动周期四榜图片",
    "0.1.0",
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
            "/排行榜 - 生成当前活动周期的最新四榜图片\n\n"
            "当前版本每榜展示前 10 名，数据来自燕云十六声排行榜。"
        )

    @filter.command("排行榜")
    async def latest_rank(self, event: AstrMessageEvent):
        """生成当前活动周期的四榜图片。"""
        image_path = ""
        try:
            snapshot = await self.rank_service.get_latest()
            handle, image_path = tempfile.mkstemp(
                prefix="yysls_rank_",
                suffix=".png",
            )
            os.close(handle)
            self.renderer.render(snapshot, image_path)
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

