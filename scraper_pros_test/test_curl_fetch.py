#!/usr/bin/env python3
"""CLI for å teste fetch_html_curl direkte."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

# Tillat import fra prosjektroten
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scraper.scrape_boats import fetch_html_curl  # type: ignore

DEFAULT_URL = "https://www.finn.no/mobility/search/boat?class=2188&sales_form=120"
DEFAULT_MIN_LENGTH = 1_000
SNIPPET_LENGTH = 200


def _format_snippet(html: str, length: int = SNIPPET_LENGTH) -> str:
    snippet = html[:length]
    snippet = snippet.replace("\r", " ").replace("\n", " ")
    return snippet


def run(url: str, min_length: int) -> int:
    try:
        html: Optional[str] = fetch_html_curl(url)
    except Exception as exc:  # pragma: no cover - defensive logging/exit
        print(f"Feil ved henting via curl: {exc}")
        return 1

    if html is None:
        print("fetch_html_curl returnerte None")
        return 2

    length = len(html)
    print(f"Hentet {length} tegn fra {url}")
    print("Forhåndsvisning (~200 tegn):")
    print(_format_snippet(html))

    if length < min_length:
        print(f"Responsen er kortere enn --min-length ({min_length})")
        return 3

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Test fetch_html_curl (krever at curl er installert lokalt)."
        )
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="URL som skal hentes (krever lokal curl).",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=DEFAULT_MIN_LENGTH,
        help="Minimumslengde på respons før skriptet returnerer suksess.",
    )
    args = parser.parse_args()

    exit_code = run(url=args.url, min_length=args.min_length)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
