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
st.sidebar.title("🌍 Reiseplanung")
search_city = st.sidebar.text_input("Stadt suchen", key="city_input")

st.sidebar.divider()
st.sidebar.title("🔋 Reichweite")
battery = st.sidebar.number_input("Batterie (kWh)", 10, 150, 75, step=1)
soc = st.sidebar.slider("Akku %", 0, 100, 40)
cons = st.sidebar.number_input("Verbrauch (kWh/100km)", 10, 40, 20, step=1)
range_km = int((battery * (soc / 100)) / cons * 100)
st.sidebar.metric("Reichweite", f"{range_km} km")

st.sidebar.divider()
st.sidebar.title("⚙️ Filter")
only_tesla = st.sidebar.checkbox("Nur Tesla Supercharger", key="tesla_check")
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 350, 150)
search_radius = st.sidebar.slider("Suchradius (km)", 10, 500, 150)

# --- STANDORT ---
target_lat, target_lon = None, None
if search_city:
    try:
        geo = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}", headers={'User-Agent': 'EV-Finder-V4'}).json()
        if geo: target_lat, target_lon = float(geo[0]['lat']), float(geo[0]['lon'])
    except: st.error("Suche fehlgeschlagen.")
else:
    loc = get_geolocation()
    if loc: target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

# --- KARTE & DATEN ---
st.title("⚡ EV Ultra Finder Pro")

if target_lat and target_lon:
    m = folium.Map(location=[target_lat, target_lon], zoom_start=8, tiles="cartodbpositron")
    folium.Circle([target_lat, target_lon], radius=range_km*1000, color="green", fill=True, fill_opacity=0.1).add_to(m)

    if API_KEY:
        # Optimierte API-Parameter für MEHR Stationen und bessere Namen
        params = {
            "key": API_KEY,
            "latitude": target_lat,
            "longitude": target_lon,
            "distance": search_radius,
            "distanceunit": "KM",
            "maxresults": 500,  # Erhöht auf 500
            "compact": "false", # Auf false gesetzt für volle Betreiber-Infos
            "verbose": "false"
        }
        
        try:
            res = requests.get("https://api.openchargemap.io/v3/poi/", params=params)
            if res.status_code == 200:
                data = res.json()
                found_count = 0
                for poi in data:
                    # Leistung berechnen
                    conns = poi.get('Connections', [])
                    pwr = max([c.get('PowerKW', 0) for c in conns if c.get('PowerKW')], default=0)
                    if pwr < min_power: continue
                    
                    # Betreiber-Name (verschiedene Felder prüfen für max. Erfolg)
                    op_info = poi.get('OperatorInfo')
                    op = "Unbekannt"
                    if op_info:
                        op = op_info.get('Title') or op_info.get('Name') or "Unbekannter Betreiber"
                    
                    if only_tesla and "tesla" not in op.lower(): continue

                    # Status & Farbe
                    s_id = int(poi.get('StatusTypeID', 0))
                    s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"
                    
                    lat, lon = poi['AddressInfo']['Latitude'], poi['AddressInfo']['Longitude']
                    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
                    pop_html = f"<b>{op}</b><br>{int(pwr)} kW<br><a href='{nav_url}' target='_blank'>📍 Navigation</a>"
                    
                    folium.Marker([lat, lon], popup=folium.Popup(pop_html, max_width=200), icon=get_lightning_html(pwr, s_color)).add_to(m)
                    found_count += 1
                st.sidebar.write(f"✅ {found_count} Stationen gefunden.")
            else: st.error(f"API Fehler: {res.status_code}")
        except: st.warning("Fehler beim Datenabruf.")
    
    st_folium(m, width="100%", height=600, key="v6_map")
else:
    st.info("Bitte Standort wählen.")
