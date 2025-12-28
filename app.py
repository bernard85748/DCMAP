import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder Pro", layout="wide", page_icon="⚡")

# Falls du keinen Key hast, wird die App trotzdem laufen (nur ohne OCM-Daten)
API_KEY = st.secrets.get("OCM_API_KEY", None)

# --- SIDEBAR ---
st.sidebar.title("🌍 Reiseplanung")
search_city = st.sidebar.text_input("Stadt suchen (z.B. Berlin)", key="city_input")

st.sidebar.divider()
st.sidebar.title("🔋 Reichweite")
battery = st.sidebar.number_input("Batterie (kWh)", 10, 150, 75)
soc = st.sidebar.slider("Akku %", 0, 100, 40)
cons = st.sidebar.number_input("Verbrauch (kWh/100km)", 10, 40, 20)
range_km = int((battery * (soc / 100)) / cons * 100)
st.sidebar.metric("Reichweite", f"{range_km} km")

# --- STANDORT-LOGIK (PRIORISIERUNG) ---
target_lat, target_lon = None, None

if search_city and len(search_city) > 2:
    # Stadt-Suche via Nominatim
    try:
        geo_url = f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}"
        res = requests.get(geo_url, headers={'User-Agent': 'EV-Finder-App-v2'}).json()
        if res:
            target_lat, target_lon = float(res[0]['lat']), float(res[0]['lon'])
    except Exception as e:
        st.error(f"Fehler bei Stadtsuche: {e}")
else:
    # Nur wenn keine Stadt gesucht wird, GPS versuchen
    try:
        loc = get_geolocation()
        if loc:
            target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']
    except:
        pass

# --- KARTEN-RENDERING ---
st.title("⚡ EV Ultra Finder Pro")

if target_lat and target_lon:
    # 1. Karte erstellen
    m = folium.Map(location=[target_lat, target_lon], zoom_start=10, tiles="cartodbpositron")
    
    # 2. Reichweitenkreis
    folium.Circle(
        [target_lat, target_lon],
        radius=range_km * 1000,
        color="green",
        fill=True,
        fill_opacity=0.1
    ).add_to(m)

    # 3. Daten laden (nur wenn API Key da ist)
    if API_KEY:
        try:
            params = {
                "key": API_KEY, "latitude": target_lat, "longitude": target_lon,
                "distance": 100, "maxresults": 50, "compact": "true"
            }
            data = requests.get("https://api.openchargemap.io/v3/poi/", params=params).json()
            for poi in data:
                lat = poi['AddressInfo']['Latitude']
                lon = poi['AddressInfo']['Longitude']
                folium.Marker([lat, lon], popup=poi['AddressInfo']['Title']).add_to(m)
        except:
            st.warning("Konnte Ladestationen nicht laden, zeige nur Karte.")

    # 4. Karte anzeigen (WICHTIG: Breite auf None für Auto-Layout)
    st_folium(m, width=None, height=500, key="main_map")
    
    st.success(f"Position gefunden: {target_lat:.4f}, {target_lon:.4f}")
else:
    st.info("Bitte Stadt eingeben oder GPS-Zugriff erlauben. Falls nichts passiert, Seite neu laden.")
