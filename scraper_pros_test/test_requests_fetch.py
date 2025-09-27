"""Command-line interface to test fetching HTML from a URL using scraper.

Usage:
    python -m scraper_pros_test.test_requests_fetch --url <URL> [--min-length <length>]
"""

from __future__ import annotations

import argparse
import sys

from scraper.scrape_boats import fetch_html


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch HTML from a URL and verify minimum content length."
    )
    parser.add_argument(
        "--url",
        required=True,
        help="The URL to fetch HTML content from.",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=1000,
        help="Minimum number of characters required in the fetched HTML.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    html = fetch_html(args.url)
    if html is None:
        print(f"Failed to fetch content from {args.url}.")
        return 1

    content_length = len(html)
    if content_length < args.min_length:
        print(
            f"Fetched {content_length} characters from {args.url}, which is less than the minimum {args.min_length}."
        )
        return 1

    print(
        f"Successfully fetched {content_length} characters from {args.url}, meeting the minimum {args.min_length}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
