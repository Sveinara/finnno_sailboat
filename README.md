# 🛥️ Finn.no Sailboat Bargain Hunter

En komplett løsning for å analysere seilbåt-annonser på Finn.no, identifisere røverkjøp, og generere spørsmål til selgere om kritiske skjulte detaljer.

## 🎯 Prosjektmål

- **Identifisere røverkjøp**: Finn båter som selges under markedspris
- **Analysere diskrete faktorer**: Vurder seiltilstand, motortimer, og skjulte problemer
- **LLM-assistert evaluering**: Bruk AI til å foreslå kritiske spørsmål til selgere
- **Automatisert markedsanalyse**: Sammenlign priser mot estimert markedsverdi

## 📁 Prosjektstruktur

```
.
├── scrape_finn.py           # Hovedscriptping og parsing av Finn.no data
├── boat_analyzer.py         # Analyselogikk og markedsvurdering
├── improved_analyzer.py     # Forbedret analyse tilpasset norsk marked
├── main_analyzer.py         # Komplett pipeline med rapportering
├── download_finn_annonselister.py  # Script for å laste ned annonselister
├── seilbater_liste.csv      # Ekstraherte båtdata (50 annonser)
├── finn_seilbåt_annonseliste.txt    # HTML-data fra annonseliste
├── finn_seilbåt_enkeltannonse.txt   # HTML-data fra enkeltannonse
└── analysis_output/         # Genererte analyser og rapporter
```

## 🚀 Kjøring

### 1. Installer avhengigheter
```bash
pip install pandas beautifulsoup4 requests
```

### 2. Kjør forbedret analyse
```bash
python3 improved_analyzer.py
```

### 3. Se resultater
Analysen genererer:
- **CSV-fil**: Detaljerte data for alle båter
- **Tekstrapport**: Prioriterte røverkjøp med handlingsplan
- **JSON-data**: Strukturerte data for videre bearbeiding

## 🔧 Hovedfunksjoner

### Datautvinning
- **Automatisk parsing** av Finn.no HTML og JSON-strukturer
- **Teknisk spesifikasjon-ekstrahering**: År, lengde, merke, motordetaljer
- **Utstyr-analyse**: Identifiserer navigasjon, sikkerhet, og komfort-utstyr
- **Tilstands-evaluering**: Positive og negative indikatorer fra beskrivelser

### Markedsanalyse
- **Merke-basert verdivurdering**: Tilpassede priser per merke (Bavaria, Jeanneau, etc.)
- **Alders-depresiert prissetting**: Realistisk verdireduksjon over tid
- **Størrelsesbasert justering**: Lengde-faktor for markedsverd
- **Norsk markedstilpasning**: Justerte baselines for norske forhold

### Røverkjøp-identifikasjon
```python
# Scoring-kriterier:
if price_ratio < 0.5:      # 50%+ under marked = Excellent (4.0 poeng)
elif price_ratio < 0.7:    # 30%+ under marked = Very Good (3.0 poeng)  
elif price_ratio < 0.85:   # 15%+ under marked = Good (2.0 poeng)
```

### Risiko-evaluering
- **Kritiske røde flagg**: "defekt motor", "prosjekt", "osmose"
- **Hastighets-indikatorer**: "må selges", "urgent", "divorce"
- **Tilstands-problemer**: Skader, reparasjons-behov

## 📊 Analyseresultater

### Scoremodell (0-10 skala)
- **Bargain Score**: Kombinert vurdering av pris vs marked, tilstand, og risiko
- **Risk Level**: LOW/MEDIUM/HIGH basert på røde flagg
- **Value Score**: Forbedret scoring med norske markedsforhold

### Kategorisering
1. **🏆 Excellent Bargains** (7.5+ score, lav/medium risiko)
2. **✅ Good Bargains** (6.5-7.4 score, lav/medium risiko)  
3. **⚠️ Risky High-Score** (6.0+ score, høy risiko)

### Selger-spørsmål
Automatisk genererte spørsmål basert på:
- **Motorspesifikke**: Timer, service-historie, type
- **Røde flagg-spesifikke**: Detaljer om defekter, reparasjons-kostnader
- **Alders-spesifikke**: Refits, rigg-tilstand, skrog-behandling
- **Standard-spørsmål**: Survey, dokumentasjon, salgsgrunn

## 🔍 Eksempel på LLM-integrasjon

```python
def analyze_boat_with_llm_prompt(boat_data):
    """Generer prompt for LLM-analyse"""
    return f"""
    Analyser denne seilbåt-annonsen for investeringsverdi og skjulte problemer:
    
    BÅTDETALJER:
    - Pris: {price} kr
    - År: {year}
    - Merke: {make} {model}
    - Lengde: {length} fot
    
    BESKRIVELSE:
    {description}
    
    Vurder:
    1. Er dette et potensielt røverkjøp vs typisk markedsverdi?
    2. Hvilke røde flagg ser du i beskrivelsen?
    3. Hvilke spørsmål bør jeg stille selger før visning?
    4. Hva bør jeg inspisere nøye under visning?
    5. Ranger dealen 1-10 hvor 10 er "excellent bargain"
    """
```

## 🏗️ Teknisk arkitektur

### Pipeline-flyt
```
Data Collection → Parsing → Technical Analysis → Market Valuation → Risk Assessment → Report Generation
```

### Moduler
1. **scrape_finn.py**: HTML/JSON parsing med robuste fallback-metoder
2. **boat_analyzer.py**: Kjerne analyse-logikk og markedsvurdering
3. **improved_analyzer.py**: Norsk markedstilpasset analyse
4. **main_analyzer.py**: Komplett pipeline med rapportering

### Feilhåndtering
- **Multiple parsing methods**: JSON → Script tags → HTML structure
- **Type-safe data extraction**: Robust handling av manglende/ugyldig data
- **Graceful degradation**: Fallback-verdier for ufullstendige annonser

## 📈 Resultater fra eksempel-kjøring

```
📊 Analyzed 50 listings
🏆 Excellent Bargains: 0
✅ Good Bargains: 0  
⚠️ Risky High-Score: 0
```

**Observasjon**: Få genuine røverkjøp i denne samplingen, som indikerer et relativt effisient marked på Finn.no.

## 🔄 Fremtidige forbedringer

### 1. Utvidet datakilde
- **Historiske priser**: Trend-analyse og sesong-justeringer
- **Solgte annonser**: Reelle transaksjons-priser vs asking price
- **Flere markedsplasser**: Sammenligning med andre plattformer

### 2. Forbedret analyse
- **Foto-analyse**: AI-vurdering av båt-tilstand fra bilder
- **Geografisk prisjustering**: Regional prisvariasjons-modell
- **Utstyr-verdivurdering**: Detaljert prissetting av tilleggsutstyr

### 3. LLM-integrasjon
- **Real-time API**: Automatisk LLM-analyse av alle potensielle røverkjøp
- **Selger-kommunikasjon**: AI-genererte spørsmålsmaler
- **Risiko-prediksjon**: Forbedret risikomodell basert på tekstanalyse

### 4. Automatisering
- **Kontinuerlig overvåking**: Daglig scanning av nye annonser
- **Alerting-system**: Push-varsler for hot deals
- **Bud-anbefaling**: Foreslåtte bud basert på markedsanalyse

## 🎯 Konklusjon

Prosjektet gir et solid fundament for automatisert båt-markedsanalyse med:

**✅ Styrker:**
- Robust data-ekstrahering fra Finn.no
- Omfattende teknisk og markedsanalyse  
- Realistisk markedsvurdering for norske forhold
- Automatisk generering av selger-spørsmål
- Strukturerte, handlingsorienterte rapporter

**⚠️ Forbedringspunkter:**
- Begrenset til list-data (ikke full annonse-innhold)
- Mangler real-time LLM-integrasjon
- Trenger flere datakilder for bedre markedsvurdering
- Kunne hatt foto-analyse for tilstandsvurdering

**🚀 Fremgangsmåten er god** som proof-of-concept og kan skaleres til et komplett markedsovervåkingssystem for seilbåt-investorer.

## 📞 Kontakt

For spørsmål eller bidrag til prosjektet, se documentation i koden eller opprett en issue.

---
*Bygget med Python, BeautifulSoup, Pandas og kjærlighet til seilas* ⛵