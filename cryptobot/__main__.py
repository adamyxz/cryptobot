"""CryptoBot - 主入口点"""

import asyncio

from .cli import CryptoBot


async def main():
    """异步主函数"""
    cli = CryptoBot()
    await cli.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
