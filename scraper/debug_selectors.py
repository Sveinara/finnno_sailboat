#!/usr/bin/env python3
import argparse
import logging
import sys
import os
from typing import List

import requests
from bs4 import BeautifulSoup

# Tillat import av prosjektmoduler
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from scraper.scrape_boats import fetch_html  # type: ignore
except Exception:
    fetch_html = None  # type: ignore

DEFAULT_SELECTORS = [
    '#mobility-item-page-root',
    '#advertising-initial-state',
    '#contact-button-data',
    'script[type="application/ld+json"]',
    'dl dt',
    'p.s-text-subtle',
]

CONSENT_HINTS = [
    'consent', 'samtykke', 'privacy', 'cookie',
]


def fetch_basic_html(url: str) -> str | None:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'nb-NO,nb;q=0.9,en-US;q=0.6,en;q=0.5',
        }
        resp = requests.get(url, headers=headers, timeout=25)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logging.error(f"basic fetch feilet for {url}: {e}")
        return None


def print_selector_matches(soup: BeautifulSoup, selectors: List[str], max_each: int = 3) -> None:
    for sel in selectors:
        try:
            nodes = soup.select(sel)
        except Exception as e:
            print(f"- {sel}: SELECT ERROR: {e}")
            continue
        print(f"- {sel}: {len(nodes)} treff")
        for idx, n in enumerate(nodes[:max_each]):
            txt = n.get_text(" ", strip=True)
            snippet = (txt[:200] + '…') if len(txt) > 200 else txt
            print(f"  [{idx+1}] <{n.name}> {snippet}")


def print_keyword_contexts(html: str, keywords: List[str], context: int = 160) -> None:
    low = html.lower()
    for kw in keywords:
        key = kw.lower().strip()
        if not key:
            continue
        pos = low.find(key)
        if pos == -1:
            print(f"- '{kw}': ikke funnet")
            continue
        start = max(0, pos - context)
        end = min(len(html), pos + len(key) + context)
        chunk = html[start:end]
        print(f"- '{kw}': …{chunk}…")


def looks_like_gated(html: str) -> bool:
    low = html.lower()
    if any(h in low for h in CONSENT_HINTS):
        return True
    # Mangel på nøkkelblokker kan indikere gating
    return ('mobility-item-page-root' not in low) and ('application/ld+json' not in low)


def handle_source(name: str, html: str, selectors: List[str], keywords: List[str]) -> None:
    print(f"=== {name} ===")
    print(f"HTML lengde: {len(html)} tegn")
    if looks_like_gated(html):
        print("Hint: HTML ser ut som 'light/gated' (mangler nøkkelblokker eller inneholder consent-tekst)")
    try:
        soup = BeautifulSoup(html, 'lxml')
    except:
        print("lxml feilet, bruker html.parser...")
        soup = BeautifulSoup(html, 'html.parser')
    print("Selector-sjekk:")
    print_selector_matches(soup, selectors)
    if keywords:
        print("Keyword-kontekst:")
        print_keyword_contexts(html, keywords)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Debugg Finn item HTML for selectors og keywords")
    parser.add_argument('--urls', nargs='*', help='Item-URL(er)')
    parser.add_argument('--files', nargs='*', help='Lokal(e) HTML-fil(er)')
    parser.add_argument('--selectors', nargs='*', default=DEFAULT_SELECTORS, help='CSS-selektorer å teste')
    parser.add_argument('--keywords', nargs='*', default=['Oslo', 'Diesel'], help='Nøkkelord å søke etter')
    parser.add_argument('--use-fetch-html', action='store_true', help='Bruk scraper.fetch_html i stedet for basic requests')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    any_done = False

    # Filer først
    for fp in args.files or []:
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                html = f.read()
            handle_source(fp, html, args.selectors, args.keywords)
            any_done = True
        except Exception as e:
            logging.error(f"Kunne ikke lese {fp}: {e}")

    # URL-er
    for url in args.urls or []:
        html = None
        if args.use_fetch_html and fetch_html:
            html = fetch_html(url)
        if not html:
            html = fetch_basic_html(url)
        if not html:
            logging.error(f"Ingen HTML for {url}")
            continue
        handle_source(url, html, args.selectors, args.keywords)
        any_done = True

    if not any_done:
        print("Ingen input. Eksempel:\n  python scraper/debug_selectors.py --urls https://www.finn.no/mobility/item/420467535 --keywords Oslo Diesel --use-fetch-html")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main()) 