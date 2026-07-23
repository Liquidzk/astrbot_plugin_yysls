import asyncio
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from src.api import RankService  # noqa: E402
from src.render import RankRenderer  # noqa: E402


async def main() -> None:
    snapshot = await RankService(cache_seconds=0).get_latest()
    output = PLUGIN_ROOT / "preview.png"
    RankRenderer().render(snapshot, str(output))
    print(output)


if __name__ == "__main__":
    asyncio.run(main())

