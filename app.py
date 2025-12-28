import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder Pro", layout="wide", page_icon="⚡")
API_KEY = st.secrets.get("OCM_API_KEY", None)

def get_lightning_html(power_kw, status_color):
    """Erzeugt Icons: 1 Blitz (blau) <200kW, 2 Blitze (rot) 200-300kW, 3 Blitze (schwarz) >300kW."""
    if power_kw < 200:
        color, count = "blue", 1
    elif 200 <= power_kw <= 300:
        color, count = "red", 2
    else:
        color, count = "black", 3  # Für alles über 300kW (320, 350, 400+)

    glow = f"box-shadow: 0 0 10px {status_color}, 0 0 5px white;" if status_color != "#A9A9A9" else ""
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 60px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 14px; height: 14px; border: 2px solid white; {glow}"></div>
                    <div style="font-size: 22px; display: flex; justify-content: center; filter: drop-shadow(1px 1px 1px white);">{icons}</div>
                 </div>""",
        icon_size=(60, 40), icon_anchor=(30, 20)
    )

# --- SIDEBAR ---
st.sidebar.title("🌍 Reiseplanung")
search_city = st.sidebar.text_input("Stadt suchen (z.B. Berlin)", key="city_input")

st.sidebar.divider()
st.sidebar.title("🔋 Reichweite")
battery = st.sidebar.number_input("Batterie (kWh)", 10, 150, 75, step=1)
soc = st.sidebar.slider("Akku %", 0, 100, 40)
cons = st.sidebar.number_input("Verbrauch (kWh/100km)", 10, 40, 20, step=1)
range_km = int((battery * (soc / 100)) / cons * 100)
st.sidebar.metric("Geschätzte Reichweite", f"{range_km} km")

st.sidebar.divider()
st.sidebar.title("⚙️ Filter")
only_tesla = st.sidebar.checkbox("Nur Tesla Supercharger", key="tesla_check")
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 350, 150)
search_radius = st.sidebar.slider("Suchradius (km)", 10, 500, 150)

if st.sidebar.button("🔄 Filter zurücksetzen"):
    for key in ["city_input", "tesla_check"]:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- STANDORT-LOGIK ---
target_lat, target_lon = None, None
if search_city:
    try:
        geo = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}", headers={'User-Agent': 'EV-Finder-Pro-V6'}).json()
        if geo: target_lat, target_lon = float(geo[0]['lat']), float(geo[0]['lon'])
    except: st.error("Suche fehlgeschlagen.")
else:
    loc = get_geolocation()
    if loc:
        target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

# --- HAUPTBEREICH & KARTE ---
st.title("⚡ EV Ultra Finder Pro")

if target_lat and target_lon:
    # Basiskarte
    m = folium.Map(location=[target_lat, target_lon], zoom_start=8, tiles="cartodbpositron")
    
    # Reichweitenkreis
    folium.Circle(
        [target_lat, target_lon],
        radius=range_km * 1000,
        color="green",
        fill=True,
        fill_opacity=0.1
    ).add_to(m)

    if API_KEY:
        params = {
    "key": API_KEY,
    "latitude": target_lat,
    "longitude": target_lon,
    "distance": search_radius,
    "distanceunit": "KM",
    "maxresults": 500,
    "compact": "false",
    "verbose": "false"
}
