# scraper/scrape_boats.py
import requests
from bs4 import BeautifulSoup
import random
import time
import logging
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from typing import List, Dict, Union
from bs4.element import ResultSet, Tag
import json
from pathlib import Path
from scraper.agent_manager import UserAgentManager

# --- Konstanter for CSS Selektorer ---
AD_ARTICLE_SELECTOR = "article.relative.isolate.sf-search-ad"
LINK_SELECTOR = "a.sf-search-ad-link"
TITLE_SELECTOR = "a.sf-search-ad-link span"
SPECS_SELECTOR = "span.text-caption.font-bold.inline-block"
PRICE_SELECTOR = "span.t3.font-bold.inline-block"
# Update location and seller type selectors
LOCATION_SELECTOR = "div.text-xs span.mr-8"
SELLER_TYPE_SELECTOR = "div.text-xs span.mr-8:first-child"

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
    
    try:
        logging.info(f"Henter {url}")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        time.sleep(random.uniform(2.0, 5.0))
        return resp.text
    except requests.RequestException as e:
        logging.error(f"Feil ved henting av {url}: {e}")
        return None


def parse_finn_boats(html_content: str, scraped_at_ts: datetime) -> List[Dict[str, Union[str, int, datetime, None]]]:
    """
    Parser HTML fra Finn båt-resultatside.
    Returnerer liste av dict med annonsefelter.
    """
    try:
        # Prefer lxml if installed for more robust parsing
        parser = "lxml"
        soup = BeautifulSoup(html_content, parser)
        logging.debug(f"HTML innhold lengde: {len(html_content)}")
        ads: ResultSet[Tag] = soup.select(AD_ARTICLE_SELECTOR)
        logging.debug(f"Fant {len(ads)} annonser med selector: {AD_ARTICLE_SELECTOR}")
        parsed_ads = []

        for ad in ads:
            try:
                # --- Hent ad_id og URL ---
                link_tag = ad.select_one(LINK_SELECTOR)
                url = link_tag.get("href") if link_tag else None
                ad_id_val = link_tag.get("id", "") if link_tag else ""
                if isinstance(ad_id_val, list):
                    ad_id_val = "".join(ad_id_val)
                ad_id = ad_id_val.replace("search-ad-", "") if ad_id_val else None

                # --- Hent tittel ---
                title_tag = ad.select_one(TITLE_SELECTOR)
                title = title_tag.get_text(strip=True) if title_tag else None

                # --- Hent spesifikasjoner ---
                specs_tag = ad.select_one(SPECS_SELECTOR)
                specs_text = specs_tag.get_text(strip=True) if specs_tag else ""
                
                # Initialiser variabler
                year = None
                length_ft = None
                motor_type = None
                motor_fuel = None
                horsepower = None
                knots = None

                # Parse specs_text (f.eks. "2017 • 46 fot • Diesel • Innenbords • 8 knop • 75 hk")
                if specs_text:
                    parts = [p.strip() for p in specs_text.split("∙")]
                    for i, part in enumerate(parts):
                        # År
                        if i == 0 and part.isdigit() and len(part) == 4:
                            year = int(part)
                        
                        # Lengde
                        if "fot" in part:
                            try:
                                length_ft = float(part.replace("fot", "").strip())
                            except ValueError:
                                pass
                        
                        # Motor drivstoff
                        if any(fuel in part.lower() for fuel in ["diesel", "bensin", "hybrid", "elektrisk"]):
                            motor_fuel = part.strip()
                        
                        # Motor type
                        if any(type_ in part.lower() for type_ in ["innenbords", "utenbords", "annet"]):
                            motor_type = part.strip()
                            
                        # Hastighet
                        if "knop" in part.lower():
                            try:
                                knots = float(part.split()[0])
                            except (ValueError, IndexError):
                                pass
                        
                        # Hestekrefter
                        if "hk" in part.lower():
                            try:
                                hp_text = part.lower().replace("hk", "").strip()
                                horsepower = float(hp_text)
                            except ValueError:
                                pass

                # --- Hent pris ---
                price_tag = ad.select_one(PRICE_SELECTOR)
                price_txt = price_tag.get_text(strip=True) if price_tag else ""
                try:
                    price = int(''.join(filter(str.isdigit, price_txt)))
                except (ValueError, TypeError):
                    price = None

                # --- Oppdatert logikk for seller type og location ---
                seller_type = None
                location = None
                
                seller_loc_tag = ad.select_one(LOCATION_SELECTOR)
                if seller_loc_tag:
                    location = seller_loc_tag.get_text(strip=True)
                    
                seller_type_tag = ad.select_one(SELLER_TYPE_SELECTOR)
                if seller_type_tag:
                    seller_text = seller_type_tag.get_text(strip=True).lower()
                    if "forhandler" in seller_text:
                        seller_type = "Forhandler"
                    elif "privat" in seller_text:
                        seller_type = "Privat"

                parsed_ads.append({
                    "ad_id": ad_id,
                    "title": title,
                    "price": price,
                    "location": location,
                    "year": year,
                    "length_ft": length_ft,
                    "motor_type": motor_type,
                    "motor_fuel": motor_fuel,
                    "horsepower": horsepower,
                    "speed_knots": knots,
                    "seller_type": seller_type,
                    "ad_url": url,
                    "scraped_at": scraped_at_ts
                })

            except Exception as e:
                logging.error(f"Feil ved parsing av annonse: {e}", exc_info=True)

        logging.info(f"Parser returnerer {len(parsed_ads)} annonser denne siden")
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
            # Parse current URL to get base
            parsed_current = urlparse(current_url)
            base_url = f"{parsed_current.scheme}://{parsed_current.netloc}{parsed_current.path}"
            next_url = f"{base_url}{href}"
            logging.debug(f"Bygget next URL: {next_url}")
            return next_url
        elif href.startswith("/"):
            # Absolute path
            parsed_current = urlparse(current_url)
            base_url = f"{parsed_current.scheme}://{parsed_current.netloc}"
            next_url = f"{base_url}{href}"
            logging.debug(f"Bygget next URL: {next_url}")
            return next_url
        elif href.startswith("http"):
            # Full URL
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
    Args:
        url: Start-URL for søket 
        max_pages: Maks antall sider som skal hentes (default 50)
        output_path: Sti til JSON-fil for lagring av resultater
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

        # Use same parser as parse_finn_boats for consistency
        soup = BeautifulSoup(html, "lxml")
        scraped_at_ts = datetime.now(timezone.utc)
        page_ads = parse_finn_boats(html, scraped_at_ts)
        all_ads.extend(page_ads)
        
        logging.info(f"Hentet {len(page_ads)} annonser fra side {page}")
        
        # Finn neste side hvis den finnes
        logging.debug(f"Søker etter neste side på side {page}")
        current_url = get_next_page_url(soup, current_url)
        if not current_url:
            logging.info(f"Ingen neste side funnet på side {page}")
            break
        else:
            logging.info(f"Fant neste side: {current_url}")
            
        page += 1
        if page > max_pages:
            logging.info(f"Nådde maks antall sider ({max_pages})")
            break

    logging.info(f"Fullført parsing. Fant totalt {len(all_ads)} gyldige annonser over {page-1} sider.")
    
    if output_path:
        save_ads_to_json(all_ads, output_path)
        
    return all_ads

# Eksempel på bruk:
if __name__ == "__main__":
    # Sett opp logging med DEBUG level
    logging.basicConfig(
        level=logging.DEBUG,  # Endret til DEBUG for mer info
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    url = "https://www.finn.no/mobility/search/boat?class=2188&sales_form=120"
    output_dir = Path(__file__).parent.parent / "Data"
    output_file = output_dir / f"sailboats_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.json"
    
    ads = get_boat_ads_data(url, output_path=output_file)

