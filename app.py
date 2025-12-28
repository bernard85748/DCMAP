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
    """Icons: 1 Blitz <200kW, 2 Blitze 200-300kW, 3 Blitze >300kW."""
    if power_kw < 200:
        color, count = "blue", 1
    elif 200 <= power_kw <= 300:
        color, count = "red", 2
    else:
        color, count = "black", 3
    
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
st.sidebar.title("🌍 Steuerung")
search_city = st.sidebar.text_input("Stadt suchen", key="city_input")

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

country_options = {"Deutschland": "DE", "Frankreich": "FR", "Österreich": "AT", "Schweiz": "CH", "Italien": "IT"}
selected_countries = st.sidebar.multiselect("Länder", options=list(country_options.keys()), default=["Deutschland"])

if st.sidebar.button("🔄 Filter zurücksetzen"):
    st.session_state.city_input = ""
    st.session_state.tesla_check = False
    st.rerun()

# --- STANDORT-FINDUNG ---
default_lat, default_lon = 50.1109, 8.6821 
target_lat, target_lon = None, None

if search_city:
    try:
        geo = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}", headers={'User-Agent': 'EV-Finder-Pro'}).json()
        if geo:
            target_lat, target_lon = float(geo[0]['lat']), float(geo[0]['lon'])
    except: pass

if not target_lat:
    loc = get_geolocation()
    if loc:
        target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

final_lat = target_lat if target_lat else default_lat
final_lon = target_lon if target_lon else default_lon

# --- HAUPTTEIL ---
st.title("⚡ EV Ultra Finder Pro")

m = folium.Map(location=[final_lat, final_lon], zoom_start=8, tiles="cartodbpositron")
folium.Circle([final_lat, final_lon], radius=range_km*1000, color="green", fill=True, fill_opacity=0.1).add_to(m)

if API_KEY:
    try:
        c_codes = [country_options[c] for c in selected_countries]
        params = {
            "key": API_KEY, "latitude": final_lat, "longitude": final_lon, 
            "distance": search_radius, "compact": "false", "maxresults": 500,
            "countrycode": ",".join(c_codes)
        }
        res = requests.get("https://api.openchargemap.io/v3/poi/", params=params).json()
        
        found_count = 0
        for poi in res:
            conns = poi.get('Connections', [])
            all_pwr = [float(c.get('PowerKW', 0)) for c in conns if c.get('PowerKW')]
            pwr = max(all_pwr, default=0)
            
            if pwr >= min_power:
                op_info = poi.get('OperatorInfo')
                op_name = op_info.get('Title') if op_info else "Unbekannter Betreiber"
                
                if only_tesla and "tesla" not in op_name.lower(): continue

                s_id = int(poi.get('StatusTypeID', 0))
                s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"
                
                lat, lon = poi['AddressInfo']['Latitude'], poi['AddressInfo']['Longitude']
                nav_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
                
                pop_html = f"""
                <div style="font-family: Arial; width: 200px;">
                    <b>{op_name}</b><br>
                    Leistung: {int(pwr)} kW<br><br>
                    <a href="{nav_url}" target="_blank" style="background-color: #4CAF50; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px;">📍 Navigation starten</a>
                </div>
                """
                
                folium.Marker(
                    [lat, lon],
                    icon=get_lightning_html(pwr, s_color),
                    popup=folium.Popup(pop_html, max_width=250)
                ).add_to(m)
                found_count += 1
        
        st.sidebar.write(f"✅ {found_count} Stationen gefunden.")
    except Exception as e:
        st.sidebar.error(f"API Fehler: {e}")

# Anzeige der Karte
st_folium(m, height=600, width=None, key="map_final_v2")

if not target_lat:
    st.info("Zeige Standard-Standort (Frankfurt). Suche eine Stadt oder erlaube GPS für deine Umgebung.")
