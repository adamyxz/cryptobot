"""Base utilities for indicator scripts

All indicator scripts output CSV format for efficient token usage.
No timestamps or redundant data - order implies sequence.
"""

import argparse
from typing import List
import sys


def print_csv_header(columns: str):
    """Print CSV header

    Args:
        columns: Comma-separated column names
    """
    print(columns)


def print_csv_row(*values):
    """Print a CSV row

    Args:
        *values: Values to print
    """
    print(",".join(str(v) for v in values))


def print_error(message: str):
    """Print error in CSV format

    Args:
        message: Error message
    """
    print(f"error,{message}")


def run_indicator_cli(description: str, fetch_func):
    """Generic CLI runner for indicator scripts

    Args:
        description: Help description for the CLI
        fetch_func: Function that takes (exchange, symbol, **kwargs) and prints CSV
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--exchange', required=True, help='Exchange name')
    parser.add_argument('--symbol', required=True, help='Trading symbol')

    args = parser.parse_args()

    try:
        fetch_func(args.exchange, args.symbol)
        return 0
    except Exception as e:
        print_error(str(e))
        return 1


if __name__ == '__main__':
    print("This is a base module. Use specific indicator scripts instead.")
