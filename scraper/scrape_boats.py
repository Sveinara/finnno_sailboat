# scraper/scrape_boats.py
import requests
from bs4 import BeautifulSoup
import random
import time
import logging
import os
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from typing import List, Dict, Union
from bs4.element import ResultSet, Tag
import json
from pathlib import Path
from agent_manager import UserAgentManager

# --- Konstanter for CSS Selektorer ---
AD_ARTICLE_SELECTOR = "article.relative.isolate.sf-search-ad"
LINK_SELECTOR = "a.sf-search-ad-link"
# Behold tittel-selector, men vi bruker den ikke lenger
TITLE_SELECTOR = "a.sf-search-ad-link span"
# Specs beholdes og returneres som rå tekst
SPECS_SELECTOR = "span.text-caption.font-bold.inline-block"
PRICE_SELECTOR = "span.t3.font-bold.inline-block"

# CSS selector for the "next page" button/link - updated to match actual HTML structure
NEXT_PAGE_SELECTOR = "a[rel='next']"
BASE_URL = "https://www.finn.no"


def fetch_html(url: str) -> str | None:
    """
    Henter HTML med randomisert User-Agent og headers.
    Returnerer HTML som string, eller None hvis feiler.
    """
    ua_manager = UserAgentManager()
    headers = ua_manager.get_headers()
    cookies = ua_manager.get_cookies()

    backoffs = [0, 2, 5, 10]
    for attempt, wait in enumerate(backoffs):
        if wait:
            time.sleep(wait + random.uniform(0.0, 0.8))
        try:
            logging.info(f"Henter {url}")
            resp = requests.get(url, headers=headers, cookies=cookies, timeout=25)
            # Enkel håndtering av anti-bot/gating
            if resp.status_code in (403, 429):
                logging.warning(f"{resp.status_code} mottatt, forsøker igjen (forsøk {attempt+1}/{len(backoffs)})")
                continue
            resp.raise_for_status()
            time.sleep(random.uniform(1.2, 3.5))
            return resp.text
        except requests.RequestException as e:
            logging.error(f"Feil ved henting av {url}: {e}")
            continue
    return None


def parse_finn_boats(html_content: str, scraped_at_ts: datetime) -> List[Dict[str, Union[str, int, datetime, None]]]:
    """
    Parser HTML fra Finn båt-resultatside.
    Returnerer liste av dict med kun: ad_id, ad_url, price, specs_text, scraped_at
    """
    try:
        # Parser-fallback: prøv lxml først, deretter html.parser
        parsed_ads: list[dict] = []
        last_error: Exception | None = None
        for parser in ("lxml", "html.parser"):
            try:
                soup = BeautifulSoup(html_content, parser)
                ads: ResultSet[Tag] = soup.select(AD_ARTICLE_SELECTOR)
                logging.debug(f"[{parser}] Fant {len(ads)} annonser med selector: {AD_ARTICLE_SELECTOR}")
                parsed_ads = []

                for ad in ads:
                    try:
                        # Lenke/ad_id
                        link_tag = ad.select_one(LINK_SELECTOR)
                        href = link_tag.get("href") if link_tag else None
                        ad_id_val = link_tag.get("id", "") if link_tag else ""
                        if isinstance(ad_id_val, list):
                            ad_id_val = "".join(ad_id_val)
                        ad_id = ad_id_val.replace("search-ad-", "") if ad_id_val else None

                        # Full URL
                        ad_url: str | None = None
                        if href:
                            if href.startswith("http"):
                                ad_url = href
                            elif href.startswith("/"):
                                ad_url = f"{BASE_URL}{href}"
                            else:
                                ad_url = href

                        # Pris (som heltall om mulig)
                        price_tag = ad.select_one(PRICE_SELECTOR)
                        price_txt = price_tag.get_text(strip=True) if price_tag else ""
                        try:
                            price = int(''.join(filter(str.isdigit, price_txt))) if price_txt else None
                        except (ValueError, TypeError):
                            price = None

                        # Rå specs-tekst
                        specs_tag = ad.select_one(SPECS_SELECTOR)
                        specs_text = specs_tag.get_text(" ", strip=True) if specs_tag else ""

                        parsed_ads.append({
                            "ad_id": ad_id,
                            "ad_url": ad_url,
                            "price": price,
                            "specs_text": specs_text,
                            "scraped_at": scraped_at_ts,
                        })
                    except Exception as e:
                        logging.error(f"Feil ved parsing av annonse: {e}", exc_info=True)

                # Lyktes med denne parseren → returner
                logging.info(f"Parser ({parser}) returnerer {len(parsed_ads)} annonser denne siden")
                return parsed_ads
            except Exception as e:
                last_error = e
                logging.warning(f"Parser {parser} feilet: {e}")
                continue
        # Hvis begge feilet
        if last_error:
            raise last_error
        return parsed_ads
    
    except Exception as e:
        logging.error(f"Feil ved parsing av HTML-innhold: {e}", exc_info=True)
        return []


def get_next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    """Henter URL til neste resultatside hvis den finnes."""
    try:
        next_link = soup.select_one(NEXT_PAGE_SELECTOR)
        logging.debug(f"Fant next link: {next_link}")
        
        if not next_link:
            logging.debug("Ingen next link funnet")
            return None
            
        href = next_link.get("href")
        logging.debug(f"Next page href: {href}")
        
        if not href or not isinstance(href, str):
            logging.debug("Ingen href funnet på next link")
            return None

        # Håndter relativ URL med query params
        if href.startswith("?"):
            parsed_current = urlparse(current_url)
            base_url = f"{parsed_current.scheme}://{parsed_current.netloc}{parsed_current.path}"
            next_url = f"{base_url}{href}"
            logging.debug(f"Bygget next URL: {next_url}")
            return next_url
        elif href.startswith("/"):
            parsed_current = urlparse(current_url)
            base_url = f"{parsed_current.scheme}://{parsed_current.netloc}"
            next_url = f"{base_url}{href}"
            logging.debug(f"Bygget next URL: {next_url}")
            return next_url
        elif href.startswith("http"):
            logging.debug(f"Full URL funnet: {href}")
            return href
        else:
            logging.warning(f"Uventet next-page URL format: {href}")
            return None
        
    except Exception as e:
        logging.error(f"Feil ved parsing av next page: {e}")
        return None


def save_ads_to_json(ads: list[dict], output_path: Path) -> None:
    """Lagrer annonser til JSON-fil."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(ads, f, ensure_ascii=False, indent=2, default=str)
    logging.info(f"Lagret {len(ads)} annonser til {output_path}")


def get_boat_ads_data(url: str, max_pages: int = 50, output_path: Path | None = None) -> list[dict]:
    """
    Entry-point for Airflow.
    Henter og parser båtannonser fra gitt Finn.no-URL.
    Returnerer kun: ad_id, ad_url, price, specs_text, scraped_at
    """
    logging.info(f"Starter scraping for {url}")
    all_ads = []
    current_url = url
    page = 1

    while current_url and page <= max_pages:
        html = fetch_html(current_url)
        if not html:
            logging.error(f"Kunne ikke hente HTML for side {page}.")
            break

        scraped_at_ts = datetime.now(timezone.utc)
        page_ads = parse_finn_boats(html, scraped_at_ts)

        # Fallback: hvis 0 annonser, prøv enkel forespørsel uten headers
        if len(page_ads) == 0:
            logging.info("0 treff – prøver enkel forespørsel uten headers...")
            try:
                simple_resp = requests.get(current_url, timeout=15)
                simple_resp.raise_for_status()
                simple_html = simple_resp.text
                simple_ads = parse_finn_boats(simple_html, scraped_at_ts)
                logging.info(f"Fallback fant {len(simple_ads)} annonser")
                if len(simple_ads) > 0:
                    html = simple_html
                    page_ads = simple_ads
            except Exception as e:
                logging.warning(f"Fallback-feil: {e}")

        all_ads.extend(page_ads)
        logging.info(f"Hentet {len(page_ads)} annonser fra side {page}")

        # Finn neste side hvis den finnes (bruk tolerant parser for next-page)
        logging.debug(f"Søker etter neste side på side {page}")
        try:
            soup_for_next = BeautifulSoup(html, "html.parser")
            next_url = get_next_page_url(soup_for_next, current_url)
        except Exception as e:
            logging.warning(f"Klarte ikke å parse next-page med html.parser: {e}")
            next_url = None

        if not next_url:
            logging.info(f"Ingen neste side funnet på side {page}")
            break
        else:
            logging.info(f"Fant neste side: {next_url}")
            current_url = next_url
            
        page += 1
        if page > max_pages:
            logging.info(f"Nådde maks antall sider ({max_pages})")
            break

    logging.info(f"Fullført parsing. Fant totalt {len(all_ads)} gyldige annonser over {page-1} sider.")
    
    if output_path:
        save_ads_to_json(all_ads, output_path)
        
    return all_ads

# Eksempelkjøring lokalt
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    url = "https://www.finn.no/mobility/search/boat?class=2188&sales_form=120"
    ads = get_boat_ads_data(url)
    print(f"Antall annonser: {len(ads)}")
    print(ads[:2])

