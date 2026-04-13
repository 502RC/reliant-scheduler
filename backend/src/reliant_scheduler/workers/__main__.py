"""Allow running the worker agent as ``python -m reliant_scheduler.workers``."""

import asyncio

from reliant_scheduler.workers.agent import WorkerAgent


def main() -> None:
    agent = WorkerAgent()
    asyncio.run(agent.start())


if __name__ == "__main__":
    main()
