import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP & STYLING ---
st.set_page_config(page_title="EV Ultra Finder Pro", layout="wide", page_icon="⚡")

def get_lightning_html(power_kw, status_color):
    """Erzeugt ein Blitz-Icon basierend auf der Ladeleistung."""
    color = "blue" if power_kw < 200 else "red" if power_kw <= 300 else "black"
    count = 1 if power_kw < 200 else 2 if power_kw <= 300 else 3
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 80px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 14px; height: 14px; border: 2px solid white;"></div>
                    <div style="font-size: 22px; display: flex; justify-content: center;">{icons}</div>
                 </div>""",
        icon_size=(80, 50), icon_anchor=(40, 25)
    )

# --- DATEN-AGGREGATOR & DEDUPLIZIERUNG ---
def aggregate_stations(ocm_data, nap_fr_data):
    """Führt verschiedene Datenquellen zusammen und entfernt doppelte Einträge."""
    final_stations = []
    
    # 1. Open Charge Map (OCM) als Basis
    for poi in ocm_data:
        try:
            conns = poi.get('Connections', [])
            pwr = max([c.get('PowerKW', 0) for c in conns if c.get('PowerKW')], default=0)
            final_stations.append({
                'lat': poi['AddressInfo']['Latitude'],
                'lon': poi['AddressInfo']['Longitude'],
                'power': int(pwr),
                'op': poi.get('OperatorInfo', {}).get('Title', 'Unbekannt'),
                'status': int(poi.get('StatusTypeID', 0)),
                'source': 'OCM'
            })
        except: continue

    # 2. NAP Frankreich Daten hinzufügen & Dubletten prüfen
    for nap in nap_fr_data:
        is_duplicate = False
        for fs in final_stations:
            # Wenn Abstand < ~150m, dann Dublette
            if abs(fs['lat'] - nap['lat']) < 0.0015 and abs(fs['lon'] - nap['lon']) < 0.0015:
                is_duplicate = True
                if fs['power'] == 0: fs['power'] = nap['power']
                break
        if not is_duplicate:
            final_stations.append(nap)
            
    return final_stations

# --- SIDEBAR: NAVIGATION & REICHWEITE ---
st.sidebar.title("🌍 Reiseplanung")
search_city = st.sidebar.text_input("Stadt suchen", key="city_input")

st.sidebar.divider()
st.sidebar.title("🔋 Reichweiten-Rechner")
# Ganzzahlen für saubere Optik
battery = st.sidebar.number_input("Batterie-Größe (kWh)", 10, 150, 75, step=1)
soc = st.sidebar.slider("Aktueller Akkustand (%)", 0, 100, 40)
cons = st.sidebar.number_input("Durchschnittsverbrauch (kWh/100km)", 10, 40, 20, step=1)

# Berechnung als Ganzzahl
range_km = int((battery * (soc / 100)) / cons * 100)
st.sidebar.metric("Geschätzte Reichweite", f"{range_km} km")

st.sidebar.divider()
st.sidebar.title("⚙️ Filter")
only_tesla = st.sidebar.checkbox("Nur Tesla Supercharger", key="tesla_check")

country_options = {"Deutschland": "DE", "Frankreich": "FR", "Österreich": "AT", "Schweiz": "CH"}
selected_countries = st.sidebar.multiselect("Länder", options=list(country_options.keys()), default=["Deutschland"], key="countries_ms")

min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 350, 150, key="power_slider")
search_radius = st.sidebar.slider("Suchradius (km)", 10, 1000, 200)

if st.sidebar.button("🔄 Alle Filter zurücksetzen"):
    for key in ["city_input", "countries_ms", "power_slider", "tesla_check"]:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- HAUPTTEIL ---
st.title("⚡ EV Ultra Finder Pro")
API_KEY = st.secrets.get("OCM_API_KEY", None)

target_lat, target_lon = None, None
if search_city:
    geo_url = f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}"
    try:
        geo_res = requests.get(geo_url, headers={'User-Agent': 'EV-Finder'}).json()
        if geo_res:
            target_lat, target_lon = float(geo_res[0]['lat']), float(geo_res[0]['lon'])
    except: st.error("Suche fehlgeschlagen.")
else:
    loc = get_geolocation()
    if loc:
        target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

if target_lat and target_lon:
    # Karte initialisieren
    m = folium.Map(location=[target_lat, target_lon], zoom_start=8, tiles="cartodbpositron")
    
    # Reichweiten-Kreis (Radius in Metern)
    folium.Circle(
        [target_lat, target_lon],
        radius=range_km * 1000,
        color="green",
        fill=True,
        fill_opacity=0.1,
        popup=f"Deine Reichweite: {range_km} km"
    ).add_to(m)

    ocm_results = []
    nap_fr_results = []

    if API_KEY:
        # 1. Open Charge Map Abfrage
        c_codes = [country_options[c] for c in selected_countries]
        params = {
            "key": API_KEY, "latitude": target_lat, "longitude": target_lon, 
            "distance": search_radius, "maxresults": 500, "compact": "true",
            "countrycode": ",".join(c_codes)
        }
