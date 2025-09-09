#!/usr/bin/env python3
"""
Testscript for å verifisere at scraperen trekker ut utstyrsliste
fra FINN-annonser. Bruker samme fetch-logikk som hovedscraperen for å
unngå blokkering. Skriptet henter en eller flere URLer og skriver ut alle
utstyrsposter samt om "ccs" finnes i listen.
"""

import argparse
import logging
import os
import sys
from typing import List

# Sørg for import fra prosjektroten
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scraper.scrape_boats import fetch_html  # type: ignore
from scraper.parse_item import parse_item_html  # type: ignore


def check_equipment(url: str) -> None:
    """Hent annonse og skriv ut utstyrsliste."""
    logging.info("Henter %s", url)
    html = fetch_html(url)
    if not html:
        print(f"Kunne ikke hente eller parse: {url}")
        return
    parsed = parse_item_html(html)
    if not parsed:
        print(f"Kunne ikke parse HTML for: {url}")
        return
    normalized, _ = parsed
    equipment: List[str] = [str(it) for it in normalized.get("equipment", [])]
    print(f"\nUtstyrsliste for {url} ({len(equipment)}):")
    for item in equipment:
        print(f" - {item}")
    has_ccs = any("ccs" in item.lower() for item in equipment)
    print(f"Har CCS? {has_ccs}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test-uttrekk av 'Utstyr' fra FINN-annonser"
    )
    parser.add_argument(
        "urls", nargs="*", help="En eller flere FINN item-URLer", default=[]
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    urls = args.urls or ["https://www.finn.no/mobility/item/59906244"]
    for url in urls:
        check_equipment(url)


if __name__ == "__main__":
    main()
