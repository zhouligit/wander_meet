#!/usr/bin/env python3
"""撤换 30 天未活跃的城市大群群主（供 cron 调用）。"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import async_session_factory
from app.services.city_group_host import sweep_inactive_owners


async def main() -> None:
    async with async_session_factory() as db:
        count = await sweep_inactive_owners(db)
        await db.commit()
    print(f"sweep_inactive_owners resigned={count}")


if __name__ == "__main__":
    asyncio.run(main())
