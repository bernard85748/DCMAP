import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- API KEY ---
API_KEY = st.secrets.get("OCM_API_KEY", None)

# --- SETUP ---
st.set_page_config(
    page_title="DC Ladestationen", 
    layout="wide", 
    page_icon="⚡",
    initial_sidebar_state="collapsed" 
)

# --- CSS ---
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
<style>
    .block-container { padding: 0rem !important; }
    .found-badge {
        position: fixed; top: 60px; right: 10px; background-color: #222222;
        color: white !important; padding: 8px 12px; border-radius: 10px;
        z-index: 9999; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }
</style>
""", unsafe_allow_html=True)

def get_lightning_html(power_kw, status_color):
    # ZURÜCK ZUR ALTEN LOGIK (Punkt 2)
    if power_kw <= 200:
        color, count = "#3b82f6", 1
    elif 200 < power_kw < 350:
        color, count = "#ef4444", 2
    else:
        color, count = "#000000", 3
    
    glow = f"box-shadow: 0 0 10px {status_color}, 0 0 5px white;" if status_color != "#A9A9A9" else ""
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 0 1px;"></i>' for _ in range(count)])
    
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 60px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 14px; height: 14px; border: 2px solid white; {glow}"></div>
                    <div style="font-size: 24px; display: flex; justify-content: center; width: 100%;">{icons}</div>
                 </div>""",
        icon_size=(60, 40), icon_anchor=(30, 20)
    )

# --- STANDORT ---
loc = get_geolocation()
current_lat, current_lon = (loc['coords']['latitude'], loc['coords']['longitude']) if loc and loc.get('coords') else (None, None)

# --- SIDEBAR ---
st.sidebar.title("🚀 Zielsuche")
search_city = st.sidebar.text_input("Stadt eingeben", placeholder="z.B. München")

st.sidebar.divider()
st.sidebar.title("🔌 DC-Leistung")
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 400, 150)
hide_tesla = st.sidebar.checkbox("Tesla Supercharger ausblenden")

# --- LEGENDE ---
st.sidebar.markdown("""
<div style="background-color: #f8f9fa; padding: 12px; border-radius: 8px; border: 1px solid #ddd; color: #333;">
<b style="font-size: 14px;">Blitze (Leistung):</b><br>
<div style="margin-top: 8px;"><i class="fa fa-bolt" style="color:#3b82f6;"></i> 50 - 200 kW</div>
<div style="margin-top: 5px;"><i class="fa fa-bolt" style="color:#ef4444;"></i><i class="fa fa-bolt" style="color:#ef4444;"></i> 201 - 349 kW</div>
<div style="margin-top: 5px;"><i class="fa fa-bolt" style="color:#000;"></i><i class="fa fa-bolt" style="color:#000;"></i><i class="fa fa-bolt" style="color:#000;"></i> ≥ 350 kW</div>
<hr style="margin: 10px 0; border-color: #ccc;">
<b>Status:</b> <span style="color:#00FF00;">●</span> Frei | <span style="color:#FF0000;">●</span> Belegt
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.title("🔋 Reichweitenradius")
battery = st.sidebar.slider("Batterie (kWh)", 10, 150, 75)
soc = st.sidebar.slider("Aktueller SOC (%)", 0, 100, 20)
cons = st.sidebar.slider("Verbrauch", 10.0, 40.0, 20.0, 0.5)
range_km = int((battery * (soc / 100)) / cons * 100)

# --- ZENTRUM ---
final_lat, final_lon = (current_lat, current_lon) if current_lat else (50.1109, 8.6821)
if search_city:
    try:
        geo = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}", headers={'User-Agent': 'DC-Finder'}).json()
        if geo: final_lat, final_lon = float(geo[0]['lat']), float(geo[0]['lon'])
    except: pass

m = folium.Map(location=[final_lat, final_lon], zoom_start=11, tiles="cartodbpositron", zoom_control=False)
if current_lat:
    folium.Marker([current_lat, current_lon], icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
    folium.Circle([current_lat, current_lon], radius=range_km*1000, color="blue", fill=True, fill_opacity=0.05).add_to(m)

# --- DATEN (Punkt 3: Direkte API-Suche ohne Puffer) ---
found_count = 0
if API_KEY:
    try:
        params = {
            "key": API_KEY, 
            "latitude": final_lat, 
            "longitude": final_lon, 
            "distance": range_km, 
            "distanceunit": "KM", 
            "maxresults": 200, 
            "compact": "false", 
            "connectiontypeid": "33,30"
        }
        res = requests.get("https://api.openchargemap.io/v3/poi/", params=params).json()
        
        for poi in res:
            conns = poi.get('Connections', [])
            max_pwr, qty = 0, 0
            for c in conns:
                p = float(c.get('PowerKW', 0) or 0)
                if p > max_pwr: max_pwr = p
                qty += int(c.get('Quantity', 1) or 1)
            
            if max_pwr < min_power: continue
            op_name = poi.get('OperatorInfo', {}).get('Title', "Unbekannt")
            if hide_tesla and "tesla" in op_name.lower(): continue
            
            s_id = int(poi.get('StatusTypeID', 0) or 0)
            s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"
            addr = poi.get('AddressInfo', {})
            lat, lon = addr.get('Latitude'), addr.get('Longitude')
            
            pop_html = f'''<div style="width:180px; color:black;"><b>{int(max_pwr)} kW</b> ({qty} 🔌)<br>{op_name}<br>
            <div style="display:flex; gap:5px; margin-top:8px;">
            <a href="https://www.google.com/maps/dir/?api=1&destination={lat},{lon}" target="_blank" style="background:#4285F4; color:white; padding:8px; border-radius:5px; text-decoration:none; flex:1; text-align:center; font-size:12px;">Google</a>
            <a href="http://maps.apple.com/?daddr={lat},{lon}" target="_blank" style="background:black; color:white; padding:8px; border-radius:5px; text-decoration:none; flex:1; text-align:center; font-size:12px;">Apple</a>
            </div></div>'''
            
            folium.Marker([lat, lon], icon=get_lightning_html(max_pwr, s_color), popup=folium.Popup(pop_html, max_width=250)).add_to(m)
            found_count += 1
    except: pass

if found_count > 0:
    st.markdown(f'<div class="found-badge">⚡ {found_count} Stationen</div>', unsafe_allow_html=True)

st_folium(m, height=800, width=None, use_container_width=True, key="dc_final_rollbacked")
