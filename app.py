import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- API KEY LADEN ---
API_KEY = st.secrets.get("OCM_API_KEY", None)

# --- SETUP (Fullscreen Optimierung) ---
st.set_page_config(
    page_title="DC Ladestationen", 
    layout="wide", 
    page_icon="⚡",
    initial_sidebar_state="collapsed" 
)

# CSS für radikalen Fullscreen & schwebende Badge
st.markdown("""
    <style>
    .block-container { padding: 0rem; }
    header { visibility: hidden; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    .stApp { bottom: 0; }
    
    /* Schwebende Badge oben rechts */
    .found-badge {
        position: absolute;
        top: 10px;
        right: 10px;
        background-color: rgba(255, 255, 255, 0.9);
        padding: 5px 12px;
        border-radius: 20px;
        border: 1px solid #ccc;
        font-family: sans-serif;
        font-size: 14px;
        font-weight: bold;
        z-index: 1000;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

def get_lightning_html(power_kw, status_color):
    if power_kw < 200: color, count = "blue", 1
    elif 200 <= power_kw <= 300: color, count = "red", 2
    else: color, count = "black", 3
    glow = f"box-shadow: 0 0 10px {status_color}, 0 0 5px white;" if status_color != "#A9A9A9" else ""
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 60px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 14px; height: 14px; border: 2px solid white; {glow}"></div>
                    <div style="font-size: 24px; display: flex; justify-content: center;">{icons}</div>
                 </div>""",
        icon_size=(60, 40), icon_anchor=(30, 20)
    )

# --- SIDEBAR ---
st.sidebar.title("🚀 Filter")
search_city = st.sidebar.text_input("Zielstadt", placeholder="Suchen...", key="city_input")
search_radius = st.sidebar.slider("Radius (km)", 10, 500, 150)
st.sidebar.divider()
st.sidebar.title("⚙️ DC-Ladeleistung") 
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 400, 150)
only_tesla = st.sidebar.checkbox("Nur Tesla Supercharger")
st.sidebar.divider()
st.sidebar.title("🔋 BEV-Reichweitenradius")
battery = st.sidebar.slider("Batterie (kWh)", 10, 150, 75)
soc = st.sidebar.slider("Akku (%)", 0, 100, 40)
cons = st.sidebar.slider("Verbrauch (kWh/100km)", 10.0, 40.0, 20.0, 0.5)
range_km = int((battery * (soc / 100)) / cons * 100)

# --- STANDORT ---
default_lat, default_lon = 50.1109, 8.6821 
target_lat, target_lon = None, None
if search_city:
    try:
        geo = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}", headers={'User-Agent': 'DC-Finder-Mobile'}).json()
        if geo: target_lat, target_lon = float(geo[0]['lat']), float(geo[0]['lon'])
    except: pass
if not target_lat:
    loc = get_geolocation()
    if loc: target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

final_lat = target_lat if target_lat else default_lat
final_lon = target_lon if target_lon else default_lon

# --- KARTE & LOGIK ---
m = folium.Map(location=[final_lat, final_lon], zoom_start=9, tiles="cartodbpositron", zoom_control=False)
folium.Circle([final_lat, final_lon], radius=range_km*1000, color="green", fill=True, fill_opacity=0.1).add_to(m)

found_count = 0
if API_KEY:
    try:
        params = {"key": API_KEY, "latitude": final_lat, "longitude": final_lon, "distance": search_radius, "distanceunit": "KM", "maxresults": 500, "compact": "false", "minpowerkw": min_power, "connectiontypeid": "33,30"}
        res = requests.get("https://api.openchargemap.io/v3/poi/", params=params).json()
        for poi in res:
            conns = poi.get('Connections', [])
            pwr, total_chargers = 0, 0
            for c in conns:
                c_pwr = float(c.get('PowerKW', 0) or 0)
                if c_pwr > pwr: pwr = c_pwr
                total_chargers += int(c.get('Quantity', 1) or 1)
            if pwr < min_power: continue
            op_name = poi.get('OperatorInfo', {}).get('Title', "Unbekannt")
            if only_tesla and "tesla" not in op_name.lower(): continue
            s_id = int(poi.get('StatusTypeID', 0) or 0)
            s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"
            lat, lon = poi['AddressInfo']['Latitude'], poi['AddressInfo']['Longitude']
            g_maps, a_maps = f"http://maps.google.com/?q={lat},{lon}", f"http://maps.apple.com/?q={lat},{lon}"
            pop_html = f'<div style="width:200px;font-family:sans-serif;"><b>{op_name}</b><br>{int(pwr)} kW | {total_chargers} Stecker<br><br><a href="{g_maps}" target="_blank" style="background:#4285F4;color:white;padding:8px;text-decoration:none;border-radius:4px;display:block;text-align:center;margin-bottom:5px;">Google Maps</a><a href="{a_maps}" target="_blank" style="background:black;color:white;padding:8px;text-decoration:none;border-radius:4px;display:block;text-align:center;">Apple Maps</a></div>'
            folium.Marker([lat, lon], icon=get_lightning_html(pwr, s_color), popup=folium.Popup(pop_html, max_width=250)).add_to(m)
            found_count += 1
    except: pass

# Badge anzeigen
if found_count > 0:
    st.markdown(f'<div class="found-badge">⚡ {found_count} Stationen</div>', unsafe_allow_html=True)

st_folium(m, height=800, width=None, key="dc_final_full", use_container_width=True)
