import sys
import os
import argparse
import logging
from typing import Optional

# Ensure we can import from the same folder (scraper/)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

try:
    from scrape_boats import (
        get_boat_ads_data,
        AD_ARTICLE_SELECTOR,
        LINK_SELECTOR,
    )
except Exception as e:
    raise RuntimeError(f"Failed to import scraper module: {e}")

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "https://www.finn.no/mobility/search/boat?class=2188&sales_form=120"

def check_selectors(url: str) -> int:
    """Fetch the URL and validate that selectors match expected elements.

    Returns the number of ad elements found.
    """
    logging.info(f"Fetching URL for selector check: {url}")
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    ads = soup.select(AD_ARTICLE_SELECTOR)
    logging.info(f"Selector '{AD_ARTICLE_SELECTOR}' matched {len(ads)} elements")

    # Try to find links within first few ads
    for idx, ad in enumerate(ads[:5]):
        a = ad.select_one(LINK_SELECTOR)
        href = a.get("href") if a else None
        logging.info(f"Ad[{idx}] link via '{LINK_SELECTOR}': {href}")

    return len(ads)

def run_smoke(url: str, max_pages: Optional[int]) -> None:
    logging.info(f"Running smoke test: url={url}, max_pages={max_pages}")
    ads = get_boat_ads_data(url=url, max_pages=max_pages)
    logging.info(f"Scraped {len(ads)} ads total")

    # Print a quick sample for manual sanity check
    for item in ads[:3]:
        logging.info(
            "Sample ad: id=%s price=%s url=%s specs=%s",
            item.get("ad_id"),
            item.get("price"),
            item.get("ad_url"),
            item.get("specs_text"),
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke-test Finn scraper without Airflow")
    parser.add_argument("--url", default=DEFAULT_URL, help="Search URL to test")
    parser.add_argument("--pages", type=int, default=1, help="Max pages to scrape (smoke)")
    parser.add_argument(
        "--selectors-only",
        action="store_true",
        help="Only fetch one page and validate selectors without full scrape",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.selectors_only:
        try:
            count = check_selectors(args.url)
            print(f"OK: selector '{AD_ARTICLE_SELECTOR}' matched {count} elements")
            sys.exit(0 if count > 0 else 2)
        except Exception as e:
            logging.exception("Selector check failed")
            sys.exit(1)
    else:
        try:
            run_smoke(args.url, max_pages=args.pages)
            print("OK: scrape completed")
            sys.exit(0)
        except Exception as e:
            logging.exception("Smoke test failed")
            sys.exit(1) 