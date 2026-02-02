"""CryptoBot - Program Entry Point"""

import asyncio

from cryptobot.cli import CryptoBot


async def main():
    """Async main function"""
    cli = CryptoBot()
    await cli.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram exited")
