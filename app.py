import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder Pro", layout="wide", page_icon="⚡")

def get_lightning_html(power_kw, status_color):
    if 50 <= power_kw < 200:
        color, count = "blue", 1
    elif 200 <= power_kw <= 300:
        color, count = "red", 2
    else:
        color, count = "black", 3

    glow = f"box-shadow: 0 0 10px {status_color}, 0 0 5px white;" if status_color in ["#00FF00", "#FF0000"] else ""
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 80px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 16px; height: 16px; margin-bottom: 2px; border: 2px solid white; {glow}"></div>
                    <div style="font-size: 24px; display: flex; justify-content: center; filter: drop-shadow(1px 1px 2px white);">{icons}</div>
                 </div>""",
        icon_size=(80, 50), icon_anchor=(40, 25)
    )

# --- SIDEBAR: NAVIGATION & FILTER ---
st.sidebar.title("🌍 Reiseplanung")

# Initialisierung Session State
if 'only_tesla' not in st.session_state: st.session_state.only_tesla = False

search_city = st.sidebar.text_input("Stadt suchen", key="city_input")

st.sidebar.divider()
st.sidebar.title("🔋 Reichweiten-Rechner")
battery_cap = st.sidebar.number_input("Batterie-Größe (kWh)", 10, 150, 75)
soc_now = st.sidebar.slider("Aktueller Akkustand (%)", 0, 100, 40)
consumption = st.sidebar.number_input("Verbrauch (kWh/100km)", 10.0, 40.0, 20.0)

# Reichweite berechnen (einfache Formel: (kWh * SoC) / Verbrauch * 100)
range_km = (battery_cap * (soc_now / 100)) / consumption * 100

st.sidebar.metric("Geschätzte Reichweite", f"{int(range_km)} km")

st.sidebar.divider()
st.sidebar.title("⚙️ Filter")
only_tesla = st.sidebar.checkbox("Nur Tesla Supercharger", value=st.session_state.only_tesla, key="tesla_check")

country_options = {"Deutschland": "DE", "Österreich": "AT", "Schweiz": "CH", "Frankreich": "FR", "Italien": "IT"}
selected_countries = st.sidebar.multiselect("Länder", options=list(country_options.keys()), default=["Deutschland"], key="countries_ms")

min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 350, 150, key="power_slider")
search_radius = st.sidebar.slider("Suchradius (km)", 10, 1000, 200)

if st.sidebar.button("🔄 Reset"):
    for key in ["city_input", "countries_ms", "power_slider", "tesla_check"]:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

st.title("⚡ EV Pro Finder")
API_KEY = st.secrets.get("OCM_API_KEY", None)

# --- STANDORT ---
target_lat, target_lon = None, None
if search_city:
    geo_url = f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}"
    try:
        geo_res = requests.get(geo_url, headers={'User-Agent': 'EV-Finder-App'}).json()
        if geo_res:
            target_lat, target_lon = float(geo_res[0]['lat']), float(geo_res[0]['lon'])
    except: st.error("Stadt nicht gefunden.")
else:
    loc = get_geolocation()
    if loc:
        target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

# --- KARTE ---
if target_lat and target_lon:
    m = folium.Map(location=[target_lat, target_lon], zoom_start=8, tiles="cartodbpositron")
    
    # REICHWEITEN-KREIS EINZEICHNEN
    folium.Circle(
        location=[target_lat, target_lon],
        radius=range_km * 1000, # Umrechnung km in Meter
        color="green",
        fill=True,
        fill_opacity=0.1,
        popup=f"Deine Reichweite ({int(range_km)} km)"
    ).add_to(m)

    if API_KEY:
        params = {"key": API_KEY, "latitude": target_lat, "longitude": target_lon, "distance": search_radius, "maxresults": 500, "compact": "true"}
        if selected_countries: params["countrycode"] = ",".join([country_options[c] for c in selected_countries])
        
        try:
            response = requests.get("https://api.openchargemap.io/v3/poi/", params=params)
            data = response.json()
            
            for poi in data:
                try:
                    p_lat, p_lon = poi['AddressInfo']['Latitude'], poi['AddressInfo']['Longitude']
                    power = max([c.get('PowerKW', 0) for c in poi.get('Connections', []) if c.get('PowerKW')], default=0)
                    if power < min_power: continue
                    
                    op_title = poi.get('OperatorInfo', {}).get('Title', 'Unbekannt') or ""
                    if only_tesla and "tesla" not in op_title.lower(): continue

                    s_id = int(poi.get('StatusTypeID', 0))
                    s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"

                    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={p_lat},{p_lon}"
                    html_popup = f"<b>{op_title}</b><br>{power} kW<br><a href='{nav_url}' target='_blank'>📍 Navigieren</a>"
                    
                    folium.Marker([p_lat, p_lon], popup=folium.Popup(html_popup, max_width=200), icon=get_lightning_html(power, s_color)).add_to(m)
                except: continue
        except: st.error("API Fehler.")
            
    st_folium(m, width="100%", height=600, key="map")
else:
    st.info("Suche Standort...")
