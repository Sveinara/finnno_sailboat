import random
from typing import NamedTuple, List
from dataclasses import dataclass
import logging
import os

@dataclass
class UserAgent:
    string: str
    weight: int  # 1-10, hvor 10 er mest brukt
    viewport: str
    platform: str
    mobile: bool

class UserAgentManager:
    def __init__(self):
        self.agents = [
            # Chrome Windows (mest brukt)
            UserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                10, "1920x1080", "Windows", False
            ),
            UserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                9, "1366x768", "Windows", False
            ),
            
            # Firefox Windows
            UserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
                8, "1920x1080", "Windows", False
            ),
            
            # Edge Windows
            UserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
                7, "1920x1080", "Windows", False
            ),
            
            # Safari MacOS (middels brukt)
            UserAgent(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
                6, "2560x1600", "macOS", False
            ),
            
            # Chrome MacOS
            UserAgent(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                5, "2880x1800", "macOS", False
            ),
            
            # Mobile enheter (mindre brukt)
            UserAgent(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
                4, "390x844", "iOS", True
            ),
            UserAgent(
                "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
                3, "412x915", "Android", True
            ),
            
            # Firefox Android (minst brukt)
            UserAgent(
                "Mozilla/5.0 (Android 14; Mobile; rv:123.0) Gecko/123.0 Firefox/123.0",
                2, "412x915", "Android", True
            ),
            
            # Safari iPad
            UserAgent(
                "Mozilla/5.0 (iPad; CPU OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
                1, "1024x1366", "iOS", True
            ),
        ]

    def get_random_agent(self) -> UserAgent:
        """Returns a random user agent, preferring desktop unless SCRAPER_MOBILE=1."""
        force_mobile = os.getenv("SCRAPER_MOBILE") == "1"
        pool = self.agents if force_mobile else [a for a in self.agents if not a.mobile]
        if not pool:  # fallback safety
            pool = self.agents
        return random.choices(
            pool,
            weights=[agent.weight for agent in pool],
            k=1
        )[0]

    def get_headers(self) -> dict:
        """Returns complete headers for a random user agent"""
        agent = self.get_random_agent()
        width = agent.viewport.split('x')[0]
        
        headers = {
            "User-Agent": agent.string,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "nb-NO,nb;q=0.9,no-NO;q=0.8,no;q=0.7,en-US;q=0.6,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.finn.no/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Viewport-Width": width,
            "Sec-CH-UA-Mobile": "?1" if agent.mobile else "?0",
            "Sec-CH-UA-Platform": f'"{agent.platform}"',
        }
        logging.info(f"Using UA (mobile={agent.mobile}, platform={agent.platform}): {agent.string}")
        return headers

    def get_cookies(self) -> dict:
        """Returner et sett med trygge standard-cookies som ofte tillater rendering uten CMP-blokk.
        Kan overskrives via env: FINN_COOKIES="name=value; other=value""" 
        raw = os.getenv("FINN_COOKIES")
        if raw:
            try:
                parts = [p.strip() for p in raw.split(';') if p.strip()]
                cookies = {}
                for p in parts:
                    if '=' in p:
                        k, v = p.split('=', 1)
                        cookies[k.strip()] = v.strip()
                return cookies
            except Exception:
                pass
        # Minimal consent/locale som ofte er ufarlig
        return {
            "cmpconsent": "accepted",
            "locale": "nb_NO",
        }
