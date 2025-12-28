import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="DC Ladestationen", layout="wide", page_icon="⚡")
API_KEY = st.secrets.get("OCM_API_KEY", None)

def get_lightning_html(power_kw, status_color):
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
st.sidebar.title("🚀 Filter")
search_city = st.sidebar.text_input("Zielstadt suchen", key="city_input")
search_radius = st.sidebar.slider("Radius (km)", 10, 500, 150)

# NEU: DC-Ladeleistung nach oben verschoben
st.sidebar.divider()
st.sidebar.title("⚙️ DC-Ladeleistung") 
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 400, 150)
only_tesla = st.sidebar.checkbox("Nur Tesla Supercharger")

# NEU: BEV-Reichweitenradius nach unten verschoben
st.sidebar.divider()
st.sidebar.title("🔋 BEV-Reichweitenradius")
battery = st.sidebar.slider("Batterie Kapazität (kWh)", min_value=10, max_value=150, value=75, step=1)
soc = st.sidebar.slider("Aktueller Akku (%)", 0, 100, 40)
cons = st.sidebar.slider("Verbrauch (kWh/100km)", min_value=10.0, max_value=40.0, value=20.0, step=0.5)

range_km = int((battery * (soc / 100)) / cons * 100)

# --- STANDORT ---
default_lat, default_lon = 50.1109, 8.6821 
target_lat, target_lon = None, None

if search_city:
    try:
        geo = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}", headers={'User-Agent': 'EV-Finder-V17'}).json()
        if geo: target_lat, target_lon = float(geo[0]['lat']), float(geo[0]['lon'])
    except: pass

if not target_lat:
    loc = get_geolocation()
    if loc: target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

final_lat = target_lat if target_lat else default_lat
final_lon = target_lon if target_lon else default_lon

# --- KARTE ---
st.title("⚡ DC Ladestationen")

m = folium.Map(location=[final_lat, final_lon], zoom_start=8, tiles="cartodbpositron")
folium.Circle([final_lat, final_lon], radius=range_km*1000, color="green", fill=True, fill_opacity=0.1).add_to(m)

if API_KEY:
    try:
        params = {
            "key": API_KEY,
            "latitude": final_lat,
            "longitude": final_lon,
            "distance": search_radius,
            "distanceunit": "KM",
            "maxresults": 500,
            "compact": "false",
            "minpowerkw": min_power,
            "connectiontypeid": "33,30", 
            "verbose": "false"
        }
        res = requests.get("https://api.openchargemap.io/v3/poi/", params=params).json()
        
        found_count = 0
        for poi in res:
            conns = poi.get('Connections', [])
            pwr = 0
            total_chargers = 0
            for c in conns:
                c_pwr = float(c.get('PowerKW', 0) or 0)
                if c_pwr > pwr: pwr = c_pwr
                total_chargers += int(c.get('Quantity', 1) or 1)

            if pwr < min_power:
                continue
            
            op_info = poi.get('OperatorInfo')
            op_name = op_info.get('Title') if op_info else "Unbekannter Betreiber"
            if only_tesla and "tesla" not in op_name.lower():
                continue

            s_id = int(poi.get('StatusTypeID', 0) or 0)
            if s_id in [10, 15, 50]:
                s_color = "#00FF00" 
            elif s_id in [20, 30, 75]:
                s_color = "#FF0000" 
            else:
                s_color = "#A9A9A9" 
            
            lat, lon = poi['AddressInfo']['Latitude'], poi['AddressInfo']['Longitude']
            nav_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
            
            pop_html = f"""
            <div style="font-family: 'Segoe UI', Arial; width: 200px; line-height: 1.4;">
                <b style="font-size: 14px; color: #333;">{op_name}</b><br>
                <hr style="margin: 5px 0; border: 0; border-top: 1px solid #eee;">
                Leistung: <span style="color: #d32f2f; font-weight: bold;">{int(pwr)} kW</span><br>
                Ladepunkte: <b>{total_chargers} Stecker</b><br><br>
                <a href="{nav_url}" target="_blank" style="background-color: #1a73e8; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; display: block; text-align: center; font-weight: bold;">📍 Navigation</a>
            </div>
            """
            
            folium.Marker(
                [lat, lon],
                icon=get_lightning_html(pwr, s_color),
                popup=folium.Popup(pop_html, max_width=250)
            ).add_to(m)
            found_count += 1
        
        st.sidebar.success(f"Gefunden: {found_count} DC-Parks")
    except Exception as e:
        st.sidebar.error(f"Datenfehler: {e}")

st_folium(m, height=600, width=None, key="dc_final_v14")
