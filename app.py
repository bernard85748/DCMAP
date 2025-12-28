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

# --- CSS (Mobile Optimierung & Design) ---
st.markdown("""
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
    if power_kw < 200: color, count = "#3b82f6", 1 
    elif 200 <= power_kw <= 300: color, count = "#ef4444", 2 
    else: color, count = "#000000", 3 
    
    glow = f"box-shadow: 0 0 10px {status_color}, 0 0 5px white;" if status_color != "#A9A9A9" else ""
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 60px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 14px; height: 14px; border: 2px solid white; {glow}"></div>
                    <div style="font-size: 24px; display: flex; justify-content: center;">{icons}</div>
                 </div>""",
        icon_size=(60, 40), icon_anchor=(30, 20)
    )

# --- SIDEBAR MIT FARBIGEN BLITZEN ---
st.sidebar.title("🚀 Zielsuche")
search_city = st.sidebar.text_input("Stadt eingeben", placeholder="z.B. Berlin", key="city_input")

st.sidebar.divider()
st.sidebar.title("⚙️ DC-Leistung") 
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 400, 150)
hide_tesla = st.sidebar.checkbox("Tesla Supercharger ausblenden")

# Die Legende nutzt jetzt die exakten Farben der Karten-Marker
st.sidebar.markdown("""
<div class="sidebar-legend">
    <strong>Blitze (Leistung):</strong><br>
    <div style="display: flex; align-items: center; gap: 8px;">
        <span style="color:#3b82f6; font-size: 20px;">⚡</span> 
        <span>&lt; 200 kW (HPC)</span>
    </div>
    <div style="display: flex; align-items: center; gap: 8px;">
        <span style="color:#ef4444; font-size: 20px;">⚡⚡</span> 
        <span>200 - 300 kW (Ultra)</span>
    </div>
    <div style="display: flex; align-items: center; gap: 8px;">
        <span style="color:#000000; font-size: 20px;">⚡⚡⚡</span> 
        <span>&gt; 300 kW (Hyper)</span>
    </div>
    <hr style="margin: 12px 0; border-color: #444;">
    <strong>Status (Punkt):</strong><br>
    <span style="color:#00FF00;">●</span> Verfügbar<br>
    <span style="color:#FF0000;">●</span> Belegt / Defekt<br>
    <span style="color:#A9A9A9;">●</span> Unbekannt
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.title("🔋 Reichweite")
battery = st.sidebar.slider("Batterie (kWh)", 10, 150, 75)
soc = st.sidebar.slider("Aktueller Stand (%)", 0, 100, 40)
cons = st.sidebar.slider("Verbrauch (kWh/100km)", 10.0, 40.0, 20.0, 0.5)

range_km = int((battery * (soc / 100)) / cons * 100)

# --- STANDORT & API LOGIK ---
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
        # API Abfrage mit Leistungspuffer
        params = {
            "key": API_KEY, "latitude": final_lat, "longitude": final_lon, 
            "distance": range_km, "distanceunit": "KM", "maxresults": 250, 
            "compact": "false", "minpowerkw": max(0, min_power - 10),
            "connectiontypeid": "33,30"
        }
        res = requests.get("https://api.openchargemap.io/v3/poi/", params=params).json()
        
        for poi in res:
            # 1. Leistung & Stecker prüfen
            conns = poi.get('Connections', [])
            max_site_pwr = 0
            total_chargers = 0
            for c in conns:
                if c:
                    p = float(c.get('PowerKW', 0) or 0)
                    if p > max_site_pwr: max_site_pwr = p
                    total_chargers += int(c.get('Quantity', 1) or 1)
            
            if max_site_pwr < min_power: continue
            
            # 2. Betreiber sicher abfragen (Fix für NoneType Error)
            op_info = poi.get('OperatorInfo')
            op_name = op_info.get('Title', "Unbekannt") if op_info else "Unbekannt"
            
            if hide_tesla and "tesla" in op_name.lower(): continue
            
            # 3. Status & Koordinaten
            s_id = int(poi.get('StatusTypeID', 0) or 0)
            s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"
            
            addr = poi.get('AddressInfo', {})
            lat, lon = addr.get('Latitude'), addr.get('Longitude')
            if lat is None or lon is None: continue
            
            # 4. Popup & Marker
            g_maps = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
            a_maps = f"http://maps.apple.com/?daddr={lat},{lon}"
            
            pop_html = f'''<div style="width:200px;font-family:sans-serif;">
                            <b style="font-size:14px;">{op_name}</b><br>
                            <span style="font-size:12px;">{int(max_site_pwr)} kW | {total_chargers} Stecker</span><br><br>
                            <a href="{g_maps}" target="_blank" style="background:#4285F4;color:white;padding:10px;text-decoration:none;border-radius:5px;display:block;text-align:center;margin-bottom:8px;font-weight:bold;">Google Maps</a>
                            <a href="{a_maps}" target="_blank" style="background:black;color:white;padding:10px;text-decoration:none;border-radius:5px;display:block;text-align:center;font-weight:bold;">Apple Maps</a>
                           </div>'''
            
            folium.Marker([lat, lon], icon=get_lightning_html(max_site_pwr, s_color), popup=folium.Popup(pop_html, max_width=250)).add_to(m)
            found_count += 1
    except Exception as e:
        st.sidebar.error(f"API Fehler: {e}")

# Treffer-Badge
if found_count > 0:
    st.markdown(f'<div class="found-badge">⚡ {found_count} Stationen</div>', unsafe_allow_html=True)

st_folium(m, height=800, width=None, key="dc_final_safe", use_container_width=True)

