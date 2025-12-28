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
search_city = st.sidebar.text_input("Stadt suchen", "")

st.sidebar.title("⚙️ Filter")
country_options = {
    "Deutschland": "DE", "Österreich": "AT", "Schweiz": "CH", 
    "Frankreich": "FR", "Italien": "IT", "Spanien": "ES", 
    "Niederlande": "NL", "Dänemark": "DK", "Norwegen": "NO"
}
selected_countries = st.sidebar.multiselect("Länder (leer lassen für alle)", options=list(country_options.keys()), default=["Deutschland"])

connector_options = {"CCS": 33, "CHAdeMO": 2, "Type 2": 25, "Tesla": 30}
selected_connectors = st.sidebar.multiselect("Stecker", options=list(connector_options.keys()), default=["CCS", "Tesla"])

selected_operators = st.sidebar.multiselect("Anbieter", ["Tesla", "EnBW", "Ionity", "Aral Pulse", "Fastned", "EWE Go"], default=[])
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 350, 150)
search_radius = st.sidebar.slider("Radius (km)", 10, 1000, 100)

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
    except: st.error("Fehler bei Stadtsuche.")
else:
    loc = get_geolocation()
    if loc:
        target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

# --- KARTE ---
if target_lat and target_lon:
    m = folium.Map(location=[target_lat, target_lon], zoom_start=8, tiles="cartodbpositron")
    
    if API_KEY:
        # Parameter dynamisch aufbauen
        params = {
            "key": API_KEY,
            "latitude": target_lat,
            "longitude": target_lon,
            "distance": search_radius,
            "maxresults": 500,
            "compact": "true",
            "verbose": "false"
        }
        
        if selected_countries:
            params["countrycode"] = ",".join([country_options[c] for c in selected_countries])
        
        if selected_connectors:
            params["connectiontypeid"] = ",".join([str(connector_options[c]) for c in selected_connectors])
        
        try:
            response = requests.get("https://api.openchargemap.io/v3/poi/", params=params)
            data = response.json()
            
            found_count = 0
            for poi in data:
                try:
                    p_lat = poi['AddressInfo']['Latitude']
                    p_lon = poi['AddressInfo']['Longitude']
                    
                    # Leistung prüfen
                    conns = poi.get('Connections', [])
                    power = max([c.get('PowerKW', 0) for c in conns if c.get('PowerKW')], default=0)
                    if power < min_power:
                        continue
                    
                    # Anbieter prüfen
                    op_title = poi.get('OperatorInfo', {}).get('Title', 'Unbekannt') or ""
                    if selected_operators:
                        if not any(op.lower() in op_title.lower() for op in selected_operators):
                            continue

                    # Status bestimmen
                    s_id = int(poi.get('StatusTypeID', 0))
                    if s_id in [10, 15, 50]: s_color, s_text = "#00FF00", "FREI"
                    elif s_id in [20, 30, 75]: s_color, s_text = "#FF0000", "BELEGT"
                    elif s_id in [100, 150, 200]: s_color, s_text = "#FFA500", "DEFEKT"
                    else: s_color, s_text = "#A9A9A9", "KEINE DATEN"

                    # Popup
                    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={p_lat},{p_lon}"
                    html_popup = f"<b>{op_title}</b><br>{power} kW<br><a href='{nav_url}' target='_blank'>📍 Navigation</a>"
                    
                    folium.Marker(
                        [p_lat, p_lon], 
                        popup=folium.Popup(html_popup, max_width=200),
                        icon=get_lightning_html(power, s_color)
                    ).add_to(m)
                    found_count += 1
                except: continue
            
            st.sidebar.write(f"✅ {found_count} Ladeparks gefunden.")
            
        except Exception as e:
            st.error(f"API Fehler: {e}")
            
    st_folium(m, width="100%", height=600, key="map")
else:
    st.info("Bitte Standort freigeben oder Stadt suchen.")
