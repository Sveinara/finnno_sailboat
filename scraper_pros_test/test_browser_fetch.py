"""CLI-verktøy for å teste Playwright-basert HTML-henting.

Skriptet krever at Playwright og Chromium er installert lokalt (for eksempel via
``playwright install``) før det kan hente HTML.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
from typing import Optional, Tuple

from scraper.parse_item import fetch_html_browser


def _fetch_with_timeout(url: str, timeout: Optional[float]) -> Tuple[Optional[str], bool]:
    if timeout is None:
        return fetch_html_browser(url), False
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fetch_html_browser, url)
        try:
            return future.result(timeout=timeout), False
        except concurrent.futures.TimeoutError:
            return None, True


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Testhenter HTML via Playwright. Krever at 'playwright install' er kjørt "
            "med Chromium tilgjengelig."
        )
    )
    parser.add_argument("--url", required=True, help="Full annonse-URL som skal hentes")
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Antall sekunder før vi gir opp henting via Playwright",
    )
    args = parser.parse_args(argv)

    timeout_value: Optional[float] = args.timeout if args.timeout > 0 else None
    html, timed_out = _fetch_with_timeout(args.url, timeout_value)

    if timed_out:
        print(
            f"Timeout etter {timeout_value:.0f} sekunder uten å hente HTML.",
            file=sys.stderr,
        )
    if not html:
        if not timed_out:
            print(
                "Kunne ikke hente HTML. Sørg for at Playwright + Chromium er installert "
                "(kjør 'playwright install') og at URL-en er gyldig.",
                file=sys.stderr,
            )
        else:
            print(
                "Sjekk at Playwright + Chromium er installert (kjør 'playwright install') "
                "og at skriptet har nettverkstilgang.",
                file=sys.stderr,
            )
        return 1

    length = len(html)
    print(f"HTML hentet! Lengde: {length} tegn.")
    if "mobility-item-page-root" in html:
        print("Fant element med id 'mobility-item-page-root'.")
    else:
        print("Fant ikke 'mobility-item-page-root' i HTML-en.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
