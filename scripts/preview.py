import asyncio
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from src.api import RankService  # noqa: E402
from src.render import RankRenderer  # noqa: E402


async def main() -> None:
    snapshot = await RankService(cache_seconds=0).get_latest()
    renderer = RankRenderer()
    overview = PLUGIN_ROOT / "preview-overview.png"
    pair = PLUGIN_ROOT / "preview-pair.png"
    detail = PLUGIN_ROOT / "preview-detail.png"
    renderer.render_overview(snapshot, str(overview))
    renderer.render_pair(snapshot.boards[:2], snapshot.updated_at, str(pair))
    renderer.render_detail(snapshot.boards[0], snapshot.updated_at, str(detail))
    print(overview)
    print(pair)
    print(detail)


if __name__ == "__main__":
    asyncio.run(main())
