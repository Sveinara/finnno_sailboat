import argparse
import logging
import os
import sys
from typing import List

# Sikre import fra prosjekt
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scraper.parse_item import parse_item_html, fetch_and_parse_item  # type: ignore


def parse_html_file(path: str) -> None:
    if not os.path.exists(path):
        logging.error(f"Fil finnes ikke: {path}")
        return
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    normalized, source_pack = parse_item_html(html)
    ad_id = normalized.get("ad_id")
    logging.info(f"OK: {os.path.basename(path)} → ad_id={ad_id}")
    print_summary(normalized)


def parse_url(url: str) -> None:
    res = fetch_and_parse_item(url)
    if not res:
        logging.error(f"Feil ved henting/parsing: {url}")
        return
    normalized, _ = res
    ad_id = normalized.get("ad_id")
    logging.info(f"OK: {url} → ad_id={ad_id}")
    print_summary(normalized)


def print_summary(n: dict) -> None:
    fields = [
        ("ad_id", n.get("ad_id")),
        ("title", n.get("title")),
        ("year", n.get("year")),
        ("make", n.get("make")),
        ("model", n.get("model")),
        ("engine_make", n.get("engine_make")),
        ("engine_type", n.get("engine_type")),
        ("engine_effect_hp", n.get("engine_effect_hp")),
        ("width_cm", n.get("width_cm")),
        ("depth_cm", n.get("depth_cm")),
        ("sleepers", n.get("sleepers")),
        ("material", n.get("material")),
        ("registration_number", n.get("registration_number")),
        ("municipality", n.get("municipality")),
        ("county", n.get("county")),
        ("postal_code", n.get("postal_code")),
        ("lat", n.get("lat")),
        ("lng", n.get("lng")),
        ("last_edited_at", n.get("last_edited_at")),
    ]
    for k, v in fields:
        print(f"{k}: {v}")
    print("-")


def main():
    parser = argparse.ArgumentParser(description="Smoke-test for item-parser")
    parser.add_argument("--files", nargs="*", help="HTML-filer å parse (f.eks. Context/annonse1.html)")
    parser.add_argument("--urls", nargs="*", help="Item-URLer å hente og parse")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ran = False
    if args.files:
        for p in args.files:
            parse_html_file(p)
            ran = True
    if args.urls:
        for u in args.urls:
            parse_url(u)
            ran = True

    if not ran:
        # Default: prøv lokale Context-filer 1..5
        default_files: List[str] = [
            os.path.join(PROJECT_ROOT, "Context", f"annonse{i}.html") for i in range(1, 6)
        ]
        logging.info("Ingen input angitt – prøver Context/annonse1-5.html hvis de finnes...")
        for p in default_files:
            if os.path.exists(p):
                parse_html_file(p)
                ran = True
        if not ran:
            logging.error("Fant ingen filer/URLer å teste. Bruk --files eller --urls.")


if __name__ == "__main__":
    main() 