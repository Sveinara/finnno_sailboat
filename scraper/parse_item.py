# scraper/parse_item.py
from __future__ import annotations

from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote
import json
import logging

# Rebruk robust fetch fra eksisterende scraper
from .scrape_boats import fetch_html


def _safe_json_loads(raw: str) -> Optional[dict]:
    """Prøv å dekode en data-props streng til JSON.
    Forsøker url-unquote 0-2 ganger før json.loads.
    """
    if not raw:
        return None
    candidates = [raw, unquote(raw), unquote(unquote(raw))]
    for i, cand in enumerate(candidates):
        try:
            return json.loads(cand)
        except Exception:
            continue
    return None


def _as_str_attr(val: Any) -> Optional[str]:
    """Normaliser BeautifulSoup-attributt som kan være str eller list[str] til str."""
    if isinstance(val, str):
        return val
    if isinstance(val, list) and val and isinstance(val[0], str):
        return val[0]
    return None


def _parse_dt(val: Any) -> Optional[datetime]:
    """Forsøk å parse tidspunkt fra ulike formater til aware datetime (UTC)."""
    try:
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(float(val), tz=timezone.utc)
        if isinstance(val, str) and val.strip():
            # Prøv ISO 8601
            try:
                dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass
    except Exception:
        return None
    return None


def _extract_from_data_props(soup: BeautifulSoup) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    root = soup.select_one('#mobility-item-page-root')
    if not root:
        return data
    # data-props kan være str eller list[str]
    dp_attr = root.get('data-props')
    dp_raw: Optional[str] = None
    if isinstance(dp_attr, str):
        dp_raw = dp_attr
    elif isinstance(dp_attr, list) and dp_attr and isinstance(dp_attr[0], str):
        dp_raw = dp_attr[0]
    dp = _safe_json_loads(dp_raw) if dp_raw else None
    if not isinstance(dp, dict):
        return data

    # Noen felt ligger under adData/ad, andre flatt – vær tolerant
    ad_candidate = dp.get('adData') or dp.get('ad') or dp
    ad: Dict[str, Any] = ad_candidate if isinstance(ad_candidate, dict) else {}

    # Grunnfelter
    data['title'] = ad.get('title') or dp.get('title')
    data['year'] = ad.get('year') or dp.get('year')
    data['make'] = (ad.get('make') or {}).get('value') if isinstance(ad.get('make'), dict) else ad.get('make')
    data['model'] = ad.get('model') or (ad.get('boat_model') if isinstance(ad, dict) else None)

    # Motor
    motor = ad.get('motor') if isinstance(ad.get('motor'), dict) else {}
    data['engine_make'] = motor.get('make') or ad.get('engine_make')
    mtype = motor.get('type') or ad.get('motor_type')
    data['engine_type'] = mtype.get('value') if isinstance(mtype, dict) else mtype
    meffect = motor.get('size') or ad.get('engine_effect')
    data['engine_effect_hp'] = None
    try:
        if isinstance(meffect, (int, float)):
            data['engine_effect_hp'] = int(meffect)
        elif isinstance(meffect, str) and meffect.strip():
            data['engine_effect_hp'] = int(''.join(ch for ch in meffect if ch.isdigit()))
    except Exception:
        pass

    # Mål og material
    def _as_int(val):
        try:
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str) and val.strip():
                return int(''.join(ch for ch in val if ch.isdigit()))
        except Exception:
            return None
        return None

    data['width_cm'] = _as_int(ad.get('width') or ad.get('width_cm'))
    data['depth_cm'] = _as_int(ad.get('depth') or ad.get('depth_cm'))
    data['sleepers'] = _as_int(ad.get('sleepers'))
    data['seats'] = _as_int(ad.get('seats'))
    data['weight_kg'] = _as_int(ad.get('weight') or ad.get('weight_kg'))

    material = ad.get('material')
    if isinstance(material, dict):
        data['material'] = material.get('value')
    else:
        data['material'] = material

    # Max speed
    data['boat_max_speed_knots'] = _as_int(ad.get('boat_max_speed'))

    # Registrering
    data['registration_number'] = ad.get('registration_number')

    # Lokasjon
    loc = ad.get('location') if isinstance(ad.get('location'), dict) else {}
    pos = loc.get('position') or {}
    data['lat'] = pos.get('lat')
    data['lng'] = pos.get('lng')

    # postale felter – kan ligge som felter eller under links
    data['postal_code'] = loc.get('postalCode') or loc.get('postal_code')
    data['municipality'] = loc.get('postName') or loc.get('municipality')
    data['county'] = loc.get('county')

    # Beskrivelse
    data['description'] = ad.get('description') or dp.get('description')

    # Bilder (prøv enkel liste om finnes)
    imgs = ad.get('images') if isinstance(ad.get('images'), list) else []
    data['images'] = imgs

    # Potensielt redigeringsinfo
    data['last_edited_at'] = _parse_dt(ad.get('edited') or dp.get('edited'))

    return data


def _extract_from_contact_button(soup: BeautifulSoup) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    script = soup.select_one('#contact-button-data')
    if not script:
        return data
    try:
        jb = json.loads(script.text)
        data['ad_id'] = str(jb.get('adId')) if jb.get('adId') is not None else None
        data['title'] = data.get('title') or jb.get('title')
        return data
    except Exception:
        return data


def _extract_from_advertising(soup: BeautifulSoup) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    script = soup.select_one('#advertising-initial-state')
    if not script:
        return data
    try:
        jb = json.loads(script.text)
        targeting = (((jb.get('config') or {}).get('adServer') or {}).get('gam') or {}).get('targeting') or []
        kv = {item.get('key'): item.get('value', []) for item in targeting if isinstance(item, dict)}
        def _first_num(key):
            v = kv.get(key)
            if not v:
                return None
            try:
                return int(str(v[0]))
            except Exception:
                return None
        def _first_str(key):
            v = kv.get(key)
            return (v or [None])[0]

        data.update({
            'year': data.get('year') or _first_num('year'),
            'width_cm': data.get('width_cm') or _first_num('width'),
            'depth_cm': data.get('depth_cm') or _first_num('depth'),
            'sleepers': data.get('sleepers') or _first_num('sleepers'),
            'engine_make': data.get('engine_make') or _first_str('engine_make'),
            'engine_type': data.get('engine_type') or _first_str('engine_type'),
            'engine_effect_hp': data.get('engine_effect_hp') or _first_num('engine_effect'),
            'boat_max_speed_knots': data.get('boat_max_speed_knots') or _first_num('boat_max_speed'),
            'material': data.get('material') or _first_str('material'),
            'make': data.get('make') or _first_str('boat_make'),
            'model': data.get('model') or _first_str('boat_model'),
            'registration_number': data.get('registration_number') or _first_str('registration_number'),
            'municipality': data.get('municipality') or _first_str('municipality'),
            'county': data.get('county') or _first_str('county'),
        })
        return data
    except Exception:
        return data


def parse_item_html(html: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Returnerer (normaliserte felt, source_pack) fra HTML.
    source_pack inneholder råutdragene for re-prosessering.
    """
    # Robust parser-fallback
    soup = None
    last_err: Optional[Exception] = None
    for parser in ('lxml', 'html.parser', 'html5lib'):
        try:
            soup = BeautifulSoup(html, parser)
            break
        except Exception as e:
            last_err = e
            logging.debug(f"BeautifulSoup parser {parser} feilet: {e}")
    if soup is None:
        logging.error(f"Alle BeautifulSoup-parsere feilet for item HTML: {last_err}")
        raise last_err if last_err else RuntimeError("Kunne ikke parse HTML")

    # Gating-deteksjon (mangler forventede noder)
    if not (soup.select_one('#mobility-item-page-root') or soup.select_one('#advertising-initial-state') or soup.select_one('#contact-button-data')):
        title = (soup.title.string.strip() if soup.title and soup.title.string else None)
        logging.warning(f"Mistenker gated/lett respons: fant ikke forventede noder. title={title!r} size={len(html)}")

    pack_data_props = _extract_from_data_props(soup)
    pack_contact = _extract_from_contact_button(soup)
    pack_adv = _extract_from_advertising(soup)

    merged: Dict[str, Any] = {}
    for src in (pack_data_props, pack_adv, pack_contact):
        for k, v in (src or {}).items():
            if v is not None and (k not in merged or merged[k] in (None, '', [])):
                merged[k] = v

    if not merged.get('ad_id'):
        link = soup.select_one('link[rel="canonical"]')
        href = _as_str_attr(link.get('href')) if link else None
        if not href:
            meta = soup.select_one('meta[property="og:url"]')
            href = _as_str_attr(meta.get('content')) if meta else None
        if href and href.rstrip('/').split('/')[-1].isdigit():
            merged['ad_id'] = href.rstrip('/').split('/')[-1]

    def _to_int(val):
        try:
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str) and val.strip():
                return int(''.join(ch for ch in val if ch.isdigit()))
        except Exception:
            return None
        return None

    for k in ('year', 'width_cm', 'depth_cm', 'sleepers', 'seats', 'engine_effect_hp', 'boat_max_speed_knots', 'weight_kg'):
        merged[k] = _to_int(merged.get(k))

    # Normaliser last_edited_at til datetime
    merged['last_edited_at'] = merged.get('last_edited_at') if isinstance(merged.get('last_edited_at'), datetime) else _parse_dt(merged.get('last_edited_at'))

    merged['scraped_at'] = datetime.now(timezone.utc)

    source_pack = {
        'data_props': pack_data_props,
        'contact': pack_contact,
        'advertising': pack_adv,
    }
    return merged, source_pack


def fetch_and_parse_item(ad_url: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    html = fetch_html(ad_url)
    if not html:
        logging.warning(f"Kunne ikke hente HTML for {ad_url}")
        return None
    try:
        parsed = parse_item_html(html)
        if not parsed:
            return None
        normalized, source = parsed
        # Fallback: utled ad_id fra URL hvis mangler
        if not normalized.get('ad_id') and ad_url:
            try:
                tail = ad_url.rstrip('/').split('/')[-1]
                if tail.isdigit():
                    normalized['ad_id'] = tail
            except Exception:
                pass
        return normalized, source
    except Exception:
        logging.exception(f"Feil ved parsing av item HTML for {ad_url}")
        return None 