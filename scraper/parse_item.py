# scraper/parse_item.py
from __future__ import annotations

from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote, urlparse, parse_qs
import json
import logging

# Rebruk robust fetch fra eksisterende scraper
from .scrape_boats import fetch_html


def _safe_json_loads(raw: Any) -> Optional[dict]:
    """Prøv å dekode en data-props streng til JSON.
    Forsøker url-unquote 0-2 ganger før json.loads.
    """
    if not raw:
        return None
    if not isinstance(raw, str):
        return None
    candidates = [raw, unquote(raw), unquote(unquote(raw))]
    for i, cand in enumerate(candidates):
        try:
            return json.loads(cand)
        except Exception:
            continue
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
    dp_raw = root.get('data-props')
    dp_obj = _safe_json_loads(dp_raw) if isinstance(dp_raw, str) else None
    if not isinstance(dp_obj, dict):
        dp_obj = {}

    # Noen felt ligger under adData/ad, andre flatt – vær tolerant
    ad_candidate = (
        dp_obj.get('adData') if isinstance(dp_obj.get('adData'), dict) else (
            dp_obj.get('ad') if isinstance(dp_obj.get('ad'), dict) else dp_obj
        )
    )
    ad: Dict[str, Any] = ad_candidate if isinstance(ad_candidate, dict) else {}

    # Grunnfelter
    data['title'] = ad.get('title') or dp_obj.get('title')
    data['year'] = ad.get('year') or dp_obj.get('year')
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
    pos = loc.get('position') if isinstance(loc.get('position'), dict) else {}
    data['lat'] = pos.get('lat')
    data['lng'] = pos.get('lng')

    # postale felter – kan ligge som felter eller under links
    data['postal_code'] = loc.get('postalCode') or loc.get('postal_code')
    data['municipality'] = loc.get('postName') or loc.get('municipality')
    data['county'] = loc.get('county')

    # Beskrivelse
    data['description'] = ad.get('description') or dp_obj.get('description')

    # Bilder (prøv enkel liste om finnes)
    imgs = ad.get('images') if isinstance(ad.get('images'), list) else []
    data['images'] = imgs

    # Potensielt redigeringsinfo
    data['last_edited_at'] = _parse_dt(ad.get('edited') or dp_obj.get('edited'))

    # Pris
    price = ad.get('price') or (ad.get('priceInfo') if isinstance(ad.get('priceInfo'), dict) else None)
    if isinstance(price, dict):
        try:
            data['price'] = int(price.get('amount')) if price.get('amount') is not None else None
        except Exception:
            data['price'] = None
        data['currency'] = price.get('currency') or 'NOK'
    elif isinstance(price, (int, float)):
        data['price'] = int(price)
        data['currency'] = 'NOK'

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


def _extract_from_dom_fallback(soup: BeautifulSoup) -> Dict[str, Any]:
    """Fallback som henter felter fra synlig DOM når JSON er utilgjengelig."""
    data: Dict[str, Any] = {}

    def _text(node):
        return node.get_text(strip=True) if node else None

    # Tittel
    h1 = soup.select_one('h1')
    if h1:
        data['title'] = _text(h1)

    # Pris (finn p med tekst Pris og h2 rett etter)
    for p in soup.find_all('p'):
        if _text(p) and _text(p).lower() == 'pris':
            container = p.parent
            if container:
                h2 = container.find('h2')
                if h2:
                    price_txt = _text(h2)
                    if price_txt:
                        digits = ''.join(ch for ch in price_txt if ch.isdigit())
                        if digits:
                            try:
                                data['price'] = int(digits)
                                data['currency'] = 'NOK'
                            except Exception:
                                pass
            break

    # Spesifikasjoner via dt/dd
    dt_to_key = {
        'modellår': 'year',
        'merke': 'make',
        'modell': 'model',
        'type motor': 'engine_type',
        'motorfabrikant': 'engine_make',
        'motorstørrelse': 'engine_effect_hp',
        'byggemateriale': 'material',
        'bredde': 'width_cm',
        'dybde': 'depth_cm',
        'soveplasser': 'sleepers',
        'sitteplasser': 'seats',
        'topphastighet': 'boat_max_speed_knots',
        'registreringsnummer': 'registration_number',
    }
    # Finn alle dt/dd par
    for dl in soup.find_all('dl'):
        for div in dl.find_all('div'):
            dt = div.find('dt')
            dd = div.find('dd')
            if not dt or not dd:
                continue
            key_raw = _text(dt)
            val_raw = _text(dd)
            if not key_raw or not val_raw:
                continue
            key = key_raw.strip().lower()
            mapped = dt_to_key.get(key)
            if not mapped:
                continue
            # Normaliser tallfelter
            if mapped in {'year', 'engine_effect_hp', 'width_cm', 'depth_cm', 'sleepers', 'seats', 'boat_max_speed_knots'}:
                try:
                    num = int(''.join(ch for ch in val_raw if ch.isdigit()))
                except Exception:
                    num = None
                data[mapped] = num
            else:
                data[mapped] = val_raw

    # FINN-kode og Sist endret
    for wrapper in soup.find_all('div'):
        labels = wrapper.find_all('p')
        if not labels:
            continue
        for idx, p in enumerate(labels):
            txt = _text(p)
            if not txt:
                continue
            txt_l = txt.lower()
            # FINN-kode
            if 'finn-kode' in txt_l and idx + 1 < len(labels):
                val = _text(labels[idx + 1])
                if val and val.isdigit():
                    data['ad_id'] = val
            # Sist endret
            if 'sist endret' in txt_l and idx + 1 < len(labels):
                val = _text(labels[idx + 1])
                if val:
                    parsed = _parse_last_edited_no(val)
                    if parsed:
                        data['last_edited_at'] = parsed

    # Sted: map-lenke med lat/lon/postalCode
    sted_section = None
    for h2 in soup.find_all('h2'):
        if _text(h2) and _text(h2).strip().lower() == 'sted':
            sted_section = h2.parent
            break
    if sted_section:
        a = sted_section.find('a', href=True)
        if a and a['href']:
            try:
                parsed = urlparse(a['href'])
                qs = parse_qs(parsed.query)
                lat = (qs.get('lat') or [None])[0]
                lon = (qs.get('lon') or [None])[0]
                postal = (qs.get('postalCode') or [None])[0]
                if lat:
                    try:
                        data['lat'] = float(lat)
                    except Exception:
                        pass
                if lon:
                    try:
                        data['lng'] = float(lon)
                    except Exception:
                        pass
                if postal and postal.isdigit():
                    data['postal_code'] = postal
            except Exception:
                pass

    return data


def _parse_last_edited_no(val: str) -> Optional[datetime]:
    """Parse norsk datoformat som '10. august 2025, 21:23' til UTC datetime."""
    try:
        s = val.strip().lower()
        # Fjern punktum etter dag
        s = s.replace('\xa0', ' ')
        parts = s.split(',')
        date_part = parts[0].strip() if parts else s
        time_part = parts[1].strip() if len(parts) > 1 else None
        # date_part forventet: '10. august 2025'
        tokens = date_part.replace('.', '').split()
        if len(tokens) < 3:
            return None
        day = int(tokens[0])
        month_name = tokens[1]
        year = int(tokens[2])
        months = {
            'januar': 1,
            'februar': 2,
            'mars': 3,
            'april': 4,
            'mai': 5,
            'juni': 6,
            'juli': 7,
            'august': 8,
            'september': 9,
            'oktober': 10,
            'november': 11,
            'desember': 12,
        }
        month = months.get(month_name)
        if not month:
            return None
        hour = 0
        minute = 0
        if time_part:
            try:
                hour = int(time_part.split(':')[0])
                minute = int(time_part.split(':')[1])
            except Exception:
                pass
        dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def parse_item_html(html: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Returnerer (normaliserte felt, source_pack) fra HTML.
    source_pack inneholder råutdragene for re-prosessering.
    """
    soup = BeautifulSoup(html, 'lxml')

    pack_data_props = _extract_from_data_props(soup)
    pack_contact = _extract_from_contact_button(soup)
    pack_adv = _extract_from_advertising(soup)
    pack_dom = _extract_from_dom_fallback(soup)

    merged: Dict[str, Any] = {}
    for src in (pack_data_props, pack_adv, pack_contact, pack_dom):
        for k, v in (src or {}).items():
            if v is not None and (k not in merged or merged[k] in (None, '', [])):
                merged[k] = v

    if not merged.get('ad_id'):
        link = soup.select_one('link[rel="canonical"]')
        href = link.get('href') if link else None
        if not href:
            meta = soup.select_one('meta[property="og:url"]')
            href = meta.get('content') if meta else None
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

    for k in ('year', 'width_cm', 'depth_cm', 'sleepers', 'seats', 'engine_effect_hp', 'boat_max_speed_knots', 'weight_kg', 'price'):
        merged[k] = _to_int(merged.get(k))

    # Normaliser last_edited_at til datetime
    merged['last_edited_at'] = merged.get('last_edited_at') if isinstance(merged.get('last_edited_at'), datetime) else _parse_dt(merged.get('last_edited_at'))

    merged['scraped_at'] = datetime.now(timezone.utc)

    source_pack = {
        'data_props': pack_data_props,
        'contact': pack_contact,
        'advertising': pack_adv,
        'dom': pack_dom,
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