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
search_city = st.sidebar.text_input("Stadt suchen (z.B. Paris)", "")

st.sidebar.title("⚙️ Filter")

# NEU: Länder Auswahl (ISO-Codes für die API)
country_options = {
    "Deutschland": "DE",
    "Österreich": "AT",
    "Schweiz": "CH",
    "Frankreich": "FR",
    "Italien": "IT",
    "Spanien": "ES",
    "Niederlande": "NL",
    "Dänemark": "DK",
    "Norwegen": "NO",
    "Schweden": "SE",
    "Belgien": "BE"
}
selected_countries = st.sidebar.multiselect(
    "Länder auswählen",
    options=list(country_options.keys()),
    default=["Deutschland"]
)

# Steckertyp Filter
connector_options = {
    "CCS (Schnelllader)": 33,
    "CHAdeMO": 2,
    "Type 2 (AC)": 25,
    "Tesla (Supercharger)": 30
}
selected_connectors = st.sidebar.multiselect(
    "Steckertypen",
    options=list(connector_options.keys()),
    default=["CCS (Schnelllader)", "Tesla (Supercharger)"]
)

# Anbieter Filter
selected_operators = st.sidebar.multiselect(
    "Bevorzugte Anbieter",
    ["Tesla", "EnBW", "Ionity", "Aral Pulse", "Fastned", "EWE Go", "Alle"],
    default=["Alle"]
)

min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 350, 150)
search_radius = st.sidebar.slider("Suchradius (km)", 10, 1000, 100)

st.title("⚡ EV Pro Finder")

API_KEY = st.secrets.get("OCM_API_KEY", None)

# --- STANDORT-LOGIK ---
target_lat, target_lon = None, None

if search_city:
    geo_url = f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}"
    try:
        geo_res = requests.get(geo_url, headers={'User-Agent': 'EV-Finder-App'}).json()
        if geo_res:
            target_lat, target_lon = float(geo_res[0]['lat']), float(geo_res[0]['lon'])
            st.success(f"📍 Ergebnisse für {search_city}")
    except:
        st.error("Fehler bei der Stadtsuche.")
else:
    loc = get_geolocation()
    if loc:
        target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

# --- KARTE UND DATEN ---
if target_lat and target_lon:
    zoom = 11 if search_radius < 50 else (8 if search_radius < 150 else 6)
    m = folium.Map(location=[target_lat, target_lon], zoom_start=zoom, tiles="cartodbpositron")
    folium.Marker([target_lat, target_lon], popup="Zentrum", icon=folium.Icon(color='blue', icon='star')).add_to(m)

    if API_KEY:
        # Länder-Codes für die API aufbereiten
        c_codes = [country_options[name] for name in selected_countries]
        country_param = ",".join(c_codes) if c_codes else ""
        
        # Steckertypen aufbereiten
        connector_ids = [connector_options[name] for name in selected_connectors]
        conn_param = ",".join(map(str, connector_ids)) if connector_ids else ""
        
        # API URL zusammenbauen (countrycode Parameter nutzt die Auswahl)
        url = f"https://api.openchargemap.io/v3/poi/?key={API_KEY}&latitude={target_lat}&longitude={target_lon}&distance={search_radius}&maxresults=1000&compact=true"
        
        if country_param:
            url += f"&countrycode={country_param}"
        if conn_param:
            url += f"&connectiontypeid={conn_param}"
        
        try:
            data = requests.get(url).json()
            for poi in data:
                try:
                    p_lat, p_lon = poi['AddressInfo']['Latitude'], poi['AddressInfo']['Longitude']
                    power = max([c.get('PowerKW', 0) for c in poi.get('Connections', []) if c.get('PowerKW')], default=0)

                    if power < min_power: continue
