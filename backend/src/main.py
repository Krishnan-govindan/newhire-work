"""NewHire.work backend entrypoint."""

import asyncio
import logging

from reboot.aio.applications import Application

from servicers.employee import EmployeeServicer, UserServicer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main() -> None:
    application = Application(
        servicers=[UserServicer, EmployeeServicer],
    )
    await application.run()


if __name__ == "__main__":
    asyncio.run(main())
