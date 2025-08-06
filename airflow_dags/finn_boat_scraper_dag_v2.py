import sys
import os
from datetime import datetime
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.bash import BashOperator
import logging

# Directly define the scraper function in this file to avoid import issues
def get_boat_ads_data_local(url: str, max_pages: int = None, output_path: str = None):
    """
    Local copy of the scrape_boats function to avoid import issues.
    This ensures the DAG always works regardless of import path problems.
    """
    import requests
    from bs4 import BeautifulSoup
    import random
    import time
    from urllib.parse import urlparse, parse_qs
    from datetime import datetime, timezone
    
    # Simple user agent rotation
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    ]
    
    def fetch_html(url: str):
        """Fetch HTML content from a URL"""
        try:
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Random delay between requests
            time.sleep(random.uniform(2.0, 5.0))
            return response.text
            
        except Exception as e:
            logging.error(f"Error fetching {url}: {e}")
            return None
    
    def parse_boat_ad(ad_element):
        """Parse a single boat ad element"""
        try:
            # Extract ad ID from href
            link_elem = ad_element.find('a', class_='sf-search-ad-link')
            if not link_elem:
                return None
                
            href = link_elem.get('href', '')
            ad_id = href.split('/')[-1] if href else None
            
            # Build full URL
            ad_url = f"https://www.finn.no{href}" if href.startswith('/') else href
            
            # Extract title
            title_elem = ad_element.find('h2') or ad_element.find('h3')
            title = title_elem.get_text(strip=True) if title_elem else "N/A"
            
            # Extract price
            price_elem = ad_element.find(class_='sf-item-price')
            price = price_elem.get_text(strip=True) if price_elem else "N/A"
            
            # Extract location
            location_elem = ad_element.find(class_='sf-item-location')
            location = location_elem.get_text(strip=True) if location_elem else "N/A"
            
            # Extract details from description
            description_elem = ad_element.find(class_='sf-item-description')
            description_text = description_elem.get_text(strip=True) if description_elem else ""
            
            # Parse details from description
            year = "N/A"
            length_ft = "N/A" 
            motor_type = "N/A"
            motor_fuel = "N/A"
            horsepower = "N/A"
            speed_knots = "N/A"
            
            if description_text:
                parts = description_text.split('•')
                for part in parts:
                    part = part.strip()
                    if any(word in part.lower() for word in ['år', 'year']):
                        year = part
                    elif 'fot' in part.lower() or 'ft' in part.lower():
                        length_ft = part
                    elif any(word in part.lower() for word in ['motor', 'engine']):
                        motor_type = part
                    elif any(word in part.lower() for word in ['diesel', 'bensin', 'electric']):
                        motor_fuel = part
                    elif any(word in part.lower() for word in ['hk', 'hp', 'horsepower']):
                        horsepower = part
                    elif any(word in part.lower() for word in ['knop', 'knots', 'mph']):
                        speed_knots = part
            
            # Seller type
            seller_elem = ad_element.find(class_='sf-item-seller-type')
            seller_type = seller_elem.get_text(strip=True) if seller_elem else "private"
            
            return {
                'ad_id': ad_id,
                'title': title,
                'price': price,
                'location': location,
                'year': year,
                'length_ft': length_ft,
                'motor_type': motor_type,
                'motor_fuel': motor_fuel,
                'horsepower': horsepower,
                'speed_knots': speed_knots,
                'seller_type': seller_type,
                'ad_url': ad_url,
                'scraped_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error parsing ad: {e}")
            return None
    
    def get_next_page_url(soup, current_url):
        """Find the next page URL"""
        try:
            next_link = soup.find('a', {'rel': 'next'})
            if not next_link:
                return None
                
            next_href = next_link.get('href')
            if not next_href:
                return None
            
            # Handle different URL formats
            if next_href.startswith('?'):
                # Relative URL starting with ?
                parsed_current = urlparse(current_url)
                base_url = f"{parsed_current.scheme}://{parsed_current.netloc}{parsed_current.path}"
                return f"{base_url}{next_href}"
            elif next_href.startswith('/'):
                # Absolute path
                parsed_current = urlparse(current_url)
                return f"{parsed_current.scheme}://{parsed_current.netloc}{next_href}"
            elif next_href.startswith('http'):
                # Full URL
                return next_href
            else:
                # Relative path
                return f"{current_url.rstrip('/')}/{next_href}"
                
        except Exception as e:
            logging.error(f"Error finding next page: {e}")
            return None
    
    # Main scraping logic
    all_ads = []
    current_url = url
    page_count = 0
    
    while current_url and (max_pages is None or page_count < max_pages):
        page_count += 1
        logging.info(f"Scraping page {page_count}: {current_url}")
        
        html = fetch_html(current_url)
        if not html:
            logging.error(f"Failed to fetch page {page_count}")
            break
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find ad containers
        ads = soup.find_all('article', class_='sf-search-ad')
        if not ads:
            logging.warning(f"No ads found on page {page_count}")
            break
            
        logging.info(f"Found {len(ads)} ads on page {page_count}")
        
        # Parse each ad
        for ad in ads:
            parsed_ad = parse_boat_ad(ad)
            if parsed_ad:
                all_ads.append(parsed_ad)
        
        # Find next page
        next_url = get_next_page_url(soup, current_url)
        if next_url:
            logging.info(f"Next page found: {next_url}")
            current_url = next_url
        else:
            logging.info("No more pages found")
            break
    
    logging.info(f"Scraping completed. Total ads collected: {len(all_ads)}")
    return all_ads

@dag(
    dag_id='finn_boat_scraper_v2', # Endret navnet for å markere at det er en ny versjon
    start_date=datetime(2023, 10, 26),
    schedule='0 7,18 * * *', # Kjører 07:00 og 18:00
    catchup=False,
    tags=['finn', 'scraping', 'boats', 'v2'],
    doc_md="""
    ### Finn.no Boat Scraper DAG (v2)
    Henter ALLE seilbåtannonser fra Finn.no ved å følge paginering.
    - **Random Delay**: Venter et tilfeldig antall sekunder (0-2 timer).
    - **Extract**: Kjører Python-funksjon for å scrape data over flere sider.
    - **Load**: Laster data inn i en staging-tabell i Postgres.
    """
)
def finn_boat_scraper_dag_v2():

    random_delay = BashOperator(
        task_id='random_delay',
        bash_command='sleep $((RANDOM % 7200))'
    )

    @task(task_id="extract_all_boat_ads")
    def extract_data():
        """
        Kaller scraper-scriptet for å hente annonsedata.
        Dette er E-steget (Extract).
        """
        # VIKTIG: Bruker den nye, korrekte URL-en fra scriptet ditt!
        FINN_URL = "https://www.finn.no/mobility/search/boat?class=2188&sales_form=120"
        
        # Vi kaller funksjonen kun med den obligatoriske input-en.
        # max_pages og output_path bruker default-verdiene.
        ads = get_boat_ads_data_local(url=FINN_URL)
        
        if not ads:
            raise ValueError("Ingen annonser funnet, stopper kjøringen.")
        return ads

    @task(task_id="load_to_staging")
    def load_data(ads: list[dict]):
        """
        Tar imot en liste med annonser og laster dem inn i
        staging_ads-tabellen i Postgres.
        Dette er L-steget (Load).
        """
        pg_hook = PostgresHook(postgres_conn_id='postgres_finn_db')
        
        # Her må vi oppdatere SQL-en til å matche de nye feltene dine!
        # Slett den gamle staging_ads tabellen og lag denne nye.
        sql_insert = """
            INSERT INTO staging_ads (
                ad_id, title, price, location, year, length_ft, motor_type,
                motor_fuel, horsepower, speed_knots, seller_type, ad_url, scraped_at
            ) VALUES (
                %(ad_id)s, %(title)s, %(price)s, %(location)s, %(year)s, %(length_ft)s,
                %(motor_type)s, %(motor_fuel)s, %(horsepower)s, %(speed_knots)s,
                %(seller_type)s, %(ad_url)s, %(scraped_at)s
            ) ON CONFLICT (ad_id, scraped_at) DO NOTHING;
        """
        
        inserted_count = 0
        for ad in ads:
            # Kjør insert og få tilbake antall rader som ble påvirket
            result = pg_hook.run(sql_insert, parameters=ad, handler=lambda cursor: cursor.rowcount)
            if result > 0:
                inserted_count += 1
            
        logging.info(f"Forsøkte å laste {len(ads)} annonser. {inserted_count} nye rader ble satt inn i staging_ads.")

    # Definerer rekkefølgen på oppgavene
    extracted_ads = extract_data()
    load_data(extracted_ads)

    # Sett avhengigheten
    random_delay >> extracted_ads

# Instansierer DAGen
finn_boat_scraper_dag_v2()