import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- API KEY LADEN ---
API_KEY = st.secrets.get("OCM_API_KEY", None)

# --- SETUP ---
st.set_page_config(
    page_title="DC Ladestationen", 
    layout="wide", 
    page_icon="⚡",
    initial_sidebar_state="collapsed" 
)

# --- CSS (Design & Icons) ---
st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
    <style>
    .block-container { padding: 0rem; }
    header { visibility: visible !important; }
    
    .found-badge {
        position: fixed;
        top: 60px;
        right: 10px;
        background-color: #222222;
        color: white !important;
        padding: 8px 12px;
        border-radius: 10px;
        z-index: 9999;
        font-weight: bold;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }
    
    .sidebar-legend {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 12px;
        border-radius: 8px;
        font-size: 14px;
        line-height: 1.6;
        border: 1px solid #444;
    }
    
    button[kind="header"] {
        background-color: rgba(255, 255, 255, 0.9) !important;
        border-radius: 50% !important;
    }
    </style>
    """, unsafe_allow_html=True)

def get_lightning_html(power_kw, status_color):
    if power_kw <= 200: 
        color, count = "#3b82f6", 1 
    elif 200 < power_kw < 350: 
        color, count = "#ef4444", 2 
    else: 
        color, count = "#000000", 3 
    
    glow = f"box-shadow: 0 0 10px {status_color}, 0 0 5px white;" if status_color != "#A9A9A9" else ""
    text_shadow = "filter: drop-shadow(0 0 2px white);" if color == "#000000" else ""
    
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 0 1px; {text_shadow}"></i>' for _ in range(count)])
    
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 60px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 14px; height: 14px; border: 2px solid white; {glow}"></div>
                    <div style="font-size: 24px; display: flex; justify-content: center;">{icons}</div>
                 </div>""",
        icon_size=(60, 40), icon_anchor=(30, 20)
    )

# --- SIDEBAR ---
st.sidebar.title("🚀 Zielsuche")
search_city = st.sidebar.text_input("Stadt eingeben", placeholder="z.B. München", key="city_input")

st.sidebar.divider()
st.sidebar.title("⚙️ DC-Leistung") 
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 400, 150)
hide_tesla = st.sidebar.checkbox("Tesla Supercharger ausblenden")

st.sidebar.markdown(f"""
<div class="sidebar-legend">
    <strong>Blitze (Leistung):</strong><br>
    <div style="display: flex; align-items: center; gap: 10px; margin-top: 5px;">
        <i class="fa fa-bolt" style="color:#3b82f6; font-size: 20px;"></i>
        <span>50 - 200 kW</span>
    </div>
    <div style="display: flex; align-items: center; gap: 10px;">
        <span style="display: flex; gap: 2px;">
            <i class="fa fa-bolt" style="color:#ef4444; font-size: 20px;"></i>
            <i class="fa fa-bolt" style="color:#ef4444; font-size: 20px;"></i>
        </span>
        <span>201 - 349 kW</span>
    </div>
    <div style="display: flex; align-items: center; gap: 10px;">
        <span style="display: flex; gap: 2px;">
            <i class="fa fa-bolt" style="color:#000000; font-size: 20px; filter: drop-shadow(0 0 1px white);"></i>
            <i class="fa fa-bolt" style="color:#000000; font-size: 20px; filter: drop-shadow(0 0 1px white);"></i>
            <i class="fa fa-bolt" style="color:#000000; font-size: 20px; filter: drop-shadow(0 0 1px white);"></i>
        </span>
        <span style="font-weight: bold;">≥ 350 kW</span>
    </div>
    <hr style="margin: 12px 0; border-color: #444;">
    <strong>Status (Punkt):</strong><br>
    <div style="display: flex; align-items: center; gap: 10px;">
        <span style="color:#00FF00; filter: drop-shadow(0 0 2px #00FF00);">●</span> 
        <span>Betriebsbereit</span>
    </div>
    <div style="display: flex; align-items: center; gap: 10px;">
        <span style="color:#FF0000; filter: drop-shadow(0 0 2px #FF0000);">●</span> 
        <span>Belegt / Defekt</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.title("🔋 Reichweite")
battery = st.sidebar.slider("Batterie (kWh)", 10, 150, 75)
soc = st.sidebar.slider("Aktueller SOC (%)", 0, 100, 20)
cons = st.sidebar.slider("Verbrauch (kWh/100km)", 10.0, 40.0, 20.0, 0.5)

range_km = int((battery * (soc / 100)) / cons * 100)

# --- STANDORT & API ---
default_lat, default_lon = 50.1109, 8.6821 
target_lat, target_lon = None, None

if search_city:
    try:
        geo = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}", headers={'User-Agent': 'DC-Finder-Final'}).json()
        if geo: target_lat, target_lon = float(geo[0]['lat']), float(geo[0]['lon'])
    except: pass

if not target_lat:
    loc = get_geolocation()
    if loc and loc.get('coords'): 
        target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

final_lat = target_lat if target_lat else default_lat
final_lon = target_lon if target_lon else default_lon

# --- KARTE ---
m = folium.Map(location=[final_lat, final_lon], zoom_start=9, tiles="cartodbpositron", zoom_control=False)
folium.Circle([final_lat, final_lon], radius=range_km*1000, color="green", fill=True, fill_opacity=0.1).add_to(m)

found_count = 0
if API_KEY:
    try:
        params = {
            "key": API_KEY, "latitude": final_lat, "longitude": final_lon, 
            "distance": range_km, "distanceunit": "KM", "maxresults": 250, 
            "compact": "false", "minpowerkw": max(0, min_power - 10),
            "connectiontypeid": "33,30"
        }
        res = requests.get("https://api.openchargemap.io/v3/poi/", params=params).json()
        
        for poi in res:
            conns = poi.get('Connections', [])
            max_site_pwr = 0
            total_chargers = 0
            for c in conns:
                if c:
                    p = float(c.get('PowerKW', 0) or 0)
                    if p > max_site_pwr: max_site_pwr = p
                    total_chargers += int(c.get('Quantity', 1) or 1)
            
            if max_site_pwr < min_power: continue
            
            op_info = poi.get('OperatorInfo')
            op_name = op_info.get('Title', "Unbekannt") if op_info else "Unbekannt"
            if hide_tesla and "tesla" in op_name.lower(): continue
            
            s_id = int(poi.get('StatusTypeID', 0) or 0)
            s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"
            
            addr = poi.get('AddressInfo', {})
            lat, lon = addr.get('Latitude'), addr.get('Longitude')
            if lat is None or lon is None: continue
            
            g_maps = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
            a_maps = f"http://maps.apple.com/?daddr={lat},{lon}"
            
            # NEUE ANORDNUNG: Zeile 1 = Leistung, Zeile 2 = Betreiber
            pop_html = f'''<div style="width:200px; font-family:sans-serif; color: black;">
                            <b style="font-size:16px;">{int(max_site_pwr)} kW</b> 
                            <span style="font-size:14px;">({total_chargers} Stecker)</span><br>
                            <span style="font-size:12px; color: #666;">{op_name}</span><br><br>
                            <a href="{g_maps}" target="_blank" style="background:#4285F4;color:white;padding:10px;text-decoration:none;border-radius:5px;display:block;text-align:center;margin-bottom:8px;font-weight:bold;">Google Maps</a>
                            <a href="{a_maps}" target="_blank" style="background:black;color:white;padding:10px;text-decoration:none;border-radius:5px;display:block;text-align:center;font-weight:bold;">Apple Maps</a>
                           </div>'''
            
            folium.Marker([lat, lon], icon=get_lightning_html(max_site_pwr, s_color), popup=folium.Popup(pop_html, max_width=250)).add_to(m)
            found_count += 1
    except Exception as e:
        st.sidebar.error(f"API Fehler: {e}")

if found_count > 0:
    st.markdown(f'<div class="found-badge">⚡ {found_count} Stationen</div>', unsafe_allow_html=True)

st_folium(m, height=800, width=None, key="dc_final_v7_popup_swap", use_container_width=True)
