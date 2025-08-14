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

# Valgfri Playwright-fallback (importeres hvis tilgjengelig)
try:
    from playwright.sync_api import sync_playwright  # type: ignore
except Exception:  # pragma: no cover
    sync_playwright = None  # type: ignore


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
        # Fallback: forsøk alle elementer med data-props
        return _extract_from_any_data_props(soup)
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


def _extract_from_any_data_props(soup: BeautifulSoup) -> Dict[str, Any]:
    """Finn og bruk første beste data-props-blokk som inneholder ad/adData."""
    data: Dict[str, Any] = {}
    nodes = soup.find_all(attrs={"data-props": True})
    for node in nodes:
        dp_raw = node.get('data-props')
        dp_obj = _safe_json_loads(dp_raw) if isinstance(dp_raw, str) else None
        if not isinstance(dp_obj, dict):
            continue
        ad_candidate = (
            dp_obj.get('adData') if isinstance(dp_obj.get('adData'), dict) else (
                dp_obj.get('ad') if isinstance(dp_obj.get('ad'), dict) else None
            )
        )
        ad = ad_candidate if isinstance(ad_candidate, dict) else None
        if not isinstance(ad, dict):
            continue
        # Rebruk felt-utledning som i _extract_from_data_props ved å lage en mini-soup med denne noden
        # eller kopiere utledningen direkte (kopierer direkte her for enkelhet og for å returnere tidlig når vi fant én)
        try:
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
            try:
                if isinstance(meffect, (int, float)):
                    data['engine_effect_hp'] = int(meffect)
                elif isinstance(meffect, str) and meffect.strip():
                    data['engine_effect_hp'] = int(''.join(ch for ch in meffect if ch.isdigit()))
            except Exception:
                pass
            # Tallfelter
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
            # Material
            material = ad.get('material')
            data['material'] = material.get('value') if isinstance(material, dict) else material
            # Max speed
            data['boat_max_speed_knots'] = _as_int(ad.get('boat_max_speed'))
            # Registrering
            data['registration_number'] = ad.get('registration_number')
            # Lokasjon
            loc = ad.get('location') if isinstance(ad.get('location'), dict) else {}
            pos = loc.get('position') if isinstance(loc.get('position'), dict) else {}
            data['lat'] = pos.get('lat')
            data['lng'] = pos.get('lng')
            data['postal_code'] = loc.get('postalCode') or loc.get('postal_code')
            data['municipality'] = loc.get('postName') or loc.get('municipality')
            data['county'] = loc.get('county')
            # Beskrivelse og redigert
            data['description'] = ad.get('description') or dp_obj.get('description')
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
        except Exception:
            continue
    return data


def _extract_from_json_ld(soup: BeautifulSoup) -> Dict[str, Any]:
    """Forsøk å hente tittel, pris, valuta, merke, modell, postnummer fra JSON-LD."""
    data: Dict[str, Any] = {}
    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            jb = json.loads(script.string or script.text or '')
        except Exception:
            continue
        # Noen sider har liste av JSON-LD blokker i én script
        candidates = jb if isinstance(jb, list) else [jb]
        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            # Tittel
            if not data.get('title'):
                name = obj.get('name') or obj.get('headline')
                if isinstance(name, str):
                    data['title'] = name
            # Pris
            offers = obj.get('offers') if isinstance(obj.get('offers'), dict) else None
            if offers:
                price = offers.get('price')
                currency = offers.get('priceCurrency') or offers.get('currency')
                try:
                    data['price'] = int(price) if price is not None else data.get('price')
                except Exception:
                    pass
                if currency and isinstance(currency, str):
                    data['currency'] = currency
            # Merke og modell
            brand = obj.get('brand')
            if isinstance(brand, dict) and not data.get('make'):
                bname = brand.get('name')
                if isinstance(bname, str):
                    data['make'] = bname
            if not data.get('model') and isinstance(obj.get('model'), (str, int)):
                data['model'] = obj.get('model')
            # Adresse/postnummer + kommunenavn/fylke
            address = obj.get('address') if isinstance(obj.get('address'), dict) else None
            if address:
                if not data.get('postal_code'):
                    pc = address.get('postalCode') or address.get('postal_code')
                    if isinstance(pc, str) and pc.isdigit():
                        data['postal_code'] = pc
                loc = address.get('addressLocality') or address.get('locality') or address.get('address_locality')
                if isinstance(loc, str) and loc.strip() and not data.get('municipality'):
                    data['municipality'] = loc.strip()
                region = address.get('addressRegion') or address.get('region') or address.get('address_region')
                if isinstance(region, str) and region.strip() and not data.get('county'):
                    data['county'] = region.strip()
        if data:
            break
    # Meta fallback for tittel
    if not data.get('title'):
        meta = soup.select_one('meta[property="og:title"]')
        if meta and meta.get('content'):
            data['title'] = meta.get('content')
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
    h1 = soup.select_one('h1, h1.t1')
    if h1:
        data['title'] = _text(h1)

    # Pris (finn p med tekst Pris og h2 rett etter)
    for p in soup.find_all('p'):
        txtp = _text(p)
        if not txtp:
            continue
        if txtp.strip().lower() == 'pris':
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
    # Ekstra fallback: direkte span.t2 inneholder ofte pris
    if 'price' not in data or data.get('price') is None:
        t2 = soup.select_one('span.t2')
        if t2:
            price_txt = _text(t2)
            if price_txt:
                digits = ''.join(ch for ch in price_txt if ch.isdigit())
                if digits:
                    try:
                        data['price'] = int(digits)
                        data['currency'] = 'NOK'
                    except Exception:
                        pass

    # Oversikts-grid: label (p eller label) med klasse s-text-subtle + verdi i p.font-bold
    label_nodes = soup.select('label.s-text-subtle, p.s-text-subtle')
    label_map = {
        'modellår': 'year',
        'type motor': 'engine_type',
        'seter': 'seats',
        'lengde': 'length_text',  # vi lagrer tekst (f.eks. "28 fot") hvis vi vil utlede senere
    }
    for lbl in label_nodes:
        key = (_text(lbl) or '').strip().lower()
        mapped = label_map.get(key)
        if not mapped:
            continue
        parent = lbl.parent
        if not parent:
            continue
        val_p = parent.find('p', class_=lambda c: c and 'font-bold' in c)
        val = _text(val_p)
        if not val:
            continue
        if mapped in {'year', 'seats'}:
            try:
                data[mapped] = int(''.join(ch for ch in val if ch.isdigit()))
            except Exception:
                pass
        else:
            data[mapped] = val

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
        'lengde i fot': 'length_ft',
        'drivstoff': 'fuel_type',
        'type': 'boat_type',
        'farge': 'color',
        'båtens beliggenhet': 'country_name',
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
            if mapped in {'year', 'engine_effect_hp', 'width_cm', 'depth_cm', 'sleepers', 'seats', 'boat_max_speed_knots', 'length_ft'}:
                try:
                    num = int(''.join(ch for ch in val_raw if ch.isdigit()))
                except Exception:
                    num = None
                data[mapped] = num
            else:
                data[mapped] = val_raw

    # Annonseinformasjon: par av p.s-text-subtle (label) + p.font-bold (verdi)
    # Først forsøk innenfor containere
    for wrap in soup.select('div .text-m, div.text-m'):
        # se etter under-diver med to p'er
        pairs = wrap.select('div > p.s-text-subtle, div > p.font-bold')
        if not pairs:
            continue
        # iterer direkte barn med p.s-text-subtle
        for container in wrap.find_all('div', recursive=False):
            lbl = container.find('p', class_=lambda c: c and 's-text-subtle' in c)
            val = container.find('p', class_=lambda c: c and 'font-bold' in c)
            lbl_txt = _text(lbl)
            val_txt = _text(val)
            if not lbl_txt or not val_txt:
                continue
            lbl_l = lbl_txt.strip().lower()
            if 'finn-kode' in lbl_l and val_txt.isdigit():
                data['ad_id'] = val_txt
            elif 'sist endret' in lbl_l:
                parsed = _parse_last_edited_no(val_txt)
                if parsed:
                    data['last_edited_at'] = parsed
    # Deretter global fallback: enhver p.s-text-subtle etterfulgt av nærmeste p.font-bold i DOM
    for lbl in soup.select('p.s-text-subtle'):
        lbl_txt = _text(lbl)
        if not lbl_txt:
            continue
        lbl_l = lbl_txt.strip().lower()
        nxt = lbl.find_next('p')
        # gå fremover til vi finner en font-bold
        while nxt and not (nxt.has_attr('class') and any('font-bold' in cls for cls in (nxt.get('class') or []))):
            nxt = nxt.find_next('p')
        if not nxt:
            continue
        val_txt = _text(nxt)
        if not val_txt:
            continue
        if 'finn-kode' in lbl_l and val_txt.isdigit():
            data['ad_id'] = val_txt
        elif 'sist endret' in lbl_l:
            parsed = _parse_last_edited_no(val_txt)
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
                if postal and isinstance(postal, str) and postal.isdigit():
                    data['postal_code'] = postal
            except Exception:
                pass
        # Forsøk også å hente kommunenavn fra synlig link-tekst (f.eks. "0250 Oslo")
        a_txt = _text(a) if a else None
        if a_txt:
            try:
                parts = a_txt.strip().split()
                if len(parts) >= 2 and parts[0].isdigit():
                    data['municipality'] = ' '.join(parts[1:])
                elif len(parts) >= 1 and not parts[0].isdigit():
                    data['municipality'] = a_txt.strip()
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
    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        logging.warning("lxml-parser feilet, faller tilbake til html.parser")
        soup = BeautifulSoup(html, 'html.parser')

    pack_data_props = _extract_from_data_props(soup)
    pack_contact = _extract_from_contact_button(soup)
    pack_adv = _extract_from_advertising(soup)
    pack_jsonld = _extract_from_json_ld(soup)
    pack_dom = _extract_from_dom_fallback(soup)

    merged: Dict[str, Any] = {}
    # Prioriter menneskelige verdier før advertising-koder
    for src in (pack_data_props, pack_jsonld, pack_dom, pack_contact, pack_adv):
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

    # Kode→tekst mapping for felter som ofte kommer som koder i advertising
    def _as_str(x: Any) -> Optional[str]:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return str(int(x))
        if isinstance(x, str):
            return x
        return None

    engine_type_map = {
        # Observasjon: 1 → Innenbords
        '1': 'Innenbords',
        # Flere koder kan legges til når observert
    }
    material_map = {
        # Observasjon: 2 → Glassfiber
        '2': 'Glassfiber',
        # Flere koder kan legges til når observert
    }

    et_code = _as_str(merged.get('engine_type'))
    if et_code and et_code in engine_type_map:
        merged['engine_type'] = engine_type_map[et_code]

    mat_code = _as_str(merged.get('material'))
    if mat_code and mat_code in material_map:
        merged['material'] = material_map[mat_code]

    # Sett standard valuta hvis pris er funnet uten currency
    if merged.get('price') is not None and not merged.get('currency'):
        merged['currency'] = 'NOK'

    # Lokasjons-postnormalisering: bruk postnummer til å sette kommunenavn når mulig (Oslo 0001–1299)
    pc = merged.get('postal_code')
    muni = merged.get('municipality')
    cty = merged.get('county')
    def _is_numeric_str(s: Any) -> bool:
        return isinstance(s, str) and s.isdigit()
    try:
        if isinstance(pc, str) and len(pc) == 4 and pc.isdigit():
            pc_int = int(pc)
            if 1 <= pc_int <= 1299:
                if (muni is None) or _is_numeric_str(muni):
                    merged['municipality'] = 'Oslo'
                if (cty is None) or _is_numeric_str(cty):
                    merged['county'] = 'Oslo'
    except Exception:
        pass

    merged['scraped_at'] = datetime.now(timezone.utc)

    source_pack = {
        'data_props': pack_data_props,
        'contact': pack_contact,
        'advertising': pack_adv,
        'jsonld': pack_jsonld,
        'dom': pack_dom,
    }
    return merged, source_pack


def _has_informative_fields(normalized: Dict[str, Any]) -> bool:
    informative_keys = [
        'title','price','year','make','model','engine_make','engine_type','engine_effect_hp',
        'width_cm','depth_cm','sleepers','seats','registration_number','municipality','county','postal_code','lat','lng'
    ]
    return any(normalized.get(k) not in (None, '', []) for k in informative_keys)


def fetch_html_browser(ad_url: str) -> Optional[str]:
    """Hent full HTML via headless Chromium hvis Playwright er tilgjengelig."""
    if not sync_playwright:
        logging.warning("Playwright ikke installert – hopper over browser-fallback")
        return None
    try:
        with sync_playwright() as p:  # type: ignore
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale="nb-NO")
            page = context.new_page()
            # Besøk forsiden for å trigge ev. samtykke
            page.goto("https://www.finn.no/", wait_until="domcontentloaded")
            for sel in ['text=Godta', 'text=Aksepter', '[data-testid="accept-all"]', '[id*="accept"]']:
                try:
                    page.click(sel, timeout=1500)
                    break
                except Exception:
                    pass
            # Besøk annonsen
            page.goto(ad_url, wait_until="domcontentloaded")
            try:
                page.wait_for_selector('#mobility-item-page-root, script[type="application/ld+json"]', timeout=6000)
            except Exception:
                pass
            html = page.content()
            browser.close()
            return html
    except Exception as e:  # pragma: no cover
        logging.warning(f"Playwright-fallback feilet: {e}")
        return None


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

        # Hvis ingen informative felter, forsøk browser-fallback én gang
        if not _has_informative_fields(normalized):
            logging.info(f"Forsøker browser-fallback for {ad_url}")
            bhtml = fetch_html_browser(ad_url)
            if bhtml:
                parsed2 = parse_item_html(bhtml)
                if parsed2:
                    normalized2, source2 = parsed2
                    if _has_informative_fields(normalized2):
                        normalized, source = normalized2, source2

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