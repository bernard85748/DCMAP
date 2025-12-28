import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder Pro", layout="wide")

# API KEY aus Secrets
API_KEY = st.secrets.get("OCM_API_KEY", None)

def get_lightning_html(power_kw, status_color):
    color = "blue" if power_kw < 200 else "red" if power_kw <= 300 else "black"
    count = 1 if power_kw < 200 else 2 if power_kw <= 300 else 3
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 60px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 12px; height: 12px; border: 2px solid white;"></div>
                    <div style="font-size: 20px; display: flex; justify-content: center; filter: drop-shadow(1px 1px 1px white);">{icons}</div>
                 </div>""",
        icon_size=(60, 40), icon_anchor=(30, 20)
    )

# --- SIDEBAR ---
st.sidebar.title("🌍 Steuerung")
search_city = st.sidebar.text_input("Stadt suchen", key="city_input")
battery = st.sidebar.number_input("Batterie (kWh)", 10, 150, 75)
soc = st.sidebar.slider("Akku %", 0, 100, 40)
cons = st.sidebar.number_input("Verbrauch", 10, 40, 20)
range_km = int((battery * (soc / 100)) / cons * 100)
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 350, 150)

# --- STANDORT-LOGIK ---
# Wir setzen einen Default (z.B. Frankfurt), damit die Karte IMMER startet
default_lat, default_lon = 50.1109, 8.6821 
target_lat, target_lon = None, None

if search_city:
    try:
        geo = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}", headers={'User-Agent': 'EV-Finder'}).json()
        if geo:
            target_lat, target_lon = float(geo[0]['lat']), float(geo[0]['lon'])
    except: pass

if not target_lat:
    loc = get_geolocation()
    if loc:
        target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

# Fallback auf Default, falls beides nicht geht
final_lat = target_lat if target_lat else default_lat
final_lon = target_lon if target_lon else default_lon

# --- HAUPTTEIL ---
st.title("⚡ EV Ultra Finder Pro")

# Karte IMMER erstellen
m = folium.Map(location=[final_lat, final_lon], zoom_start=8, tiles="cartodbpositron")
folium.Circle([final_lat, final_lon], radius=range_km*1000, color="green", fill=True, fill_opacity=0.1).add_to(m)

# Daten laden nur wenn Koordinaten von User/GPS kommen und API Key da ist
if (target_lat or search_city) and API_KEY:
    try:
        params = {"key": API_KEY, "latitude": final_lat, "longitude": final_lon, "distance": 150, "compact": "false", "maxresults": 100}
        data = requests.get("https://api.openchargemap.io/v3/poi/", params=params).json()
        for poi in data:
            conns = poi.get('Connections', [])
            pwr = max([float(c.get('PowerKW', 0)) for c in conns if c.get('PowerKW')], default=0)
            if pwr >= min_power:
                s_id = int(poi.get('StatusTypeID', 0))
                s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"
                folium.Marker(
                    [poi['AddressInfo']['Latitude'], poi['AddressInfo']['Longitude']],
                    icon=get_lightning_html(pwr, s_color),
                    popup=f"{int(pwr)} kW"
                ).add_to(m)
    except:
        st.warning("Ladestationen konnten nicht geladen werden.")

# --- DISPLAY ---
# Wir nutzen eine feste Höhe und einen neuen Key
st_folium(m, height=600, width=800, key="map_rescue_v1")

if not target_lat:
    st.info("Zeige Standard-Standort. Bitte Stadt suchen oder GPS erlauben.")
