from __future__ import annotations

import asyncio

from app.worker.behavioral_wroker import worker


if __name__ == "__main__":
    asyncio.run(worker())
