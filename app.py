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

# --- STANDORT ---
loc = get_geolocation()
current_lat, current_lon = None, None
if loc and loc.get('coords'):
    current_lat = loc['coords']['latitude']
    current_lon = loc['coords']['longitude']

# --- SIDEBAR ---
st.sidebar.title("🚀 Zielsuche")
search_city = st.sidebar.text_input("Stadt eingeben", placeholder="z.B. München", key="city_input")

st.sidebar.divider()
st.sidebar.title("🔌 DC Ladesäule")
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 400, 150)
hide_tesla = st.sidebar.checkbox("Tesla Supercharger ausblenden")

# --- LEGENDE ---
legende_html = f'''
<div style="background-color: #f0f0f0; padding: 15px; border-radius: 10px; border: 1px solid #ccc; color: #000000; font-family: sans-serif;">
    <strong style="font-size: 14px;">Blitze (Leistung):</strong><br>
    <div style="display: flex; align-items: center; margin-top: 10px;">
        <div style="width: 45px; display: flex; justify-content: center;"><i class="fa fa-bolt" style="color:#3b82f6; font-size: 18px;"></i></div>
        <span style="font-size: 13px; margin-left: 10px;">50 - 200 kW</span>
    </div>
    <div style="display: flex; align-items: center; margin-top: 8px;">
        <div style="width: 45px; display: flex; justify-content: center; white-space: nowrap;">
            <i class="fa fa-bolt" style="color:#ef4444; font-size: 18px;"></i>
            <i class="fa fa-bolt" style="color:#ef4444; font-size: 18px; margin-left: -2px;"></i>
        </div>
        <span style="font-size: 13px; margin-left: 10px;">201 - 349 kW</span>
    </div>
    <div style="display: flex; align-items: center; margin-top: 8px;">
        <div style="width: 45px; display: flex; justify-content: center; white-space: nowrap;">
            <i class="fa fa-bolt" style="color:#000000; font-size: 18px; filter: drop-shadow(0 0 1px white);"></i>
            <i class="fa fa-bolt" style="color:#000000; font-size: 18px; filter: drop-shadow(0 0 1px white); margin-left: -2px;"></i>
            <i class="fa fa-bolt" style="color:#000000; font-size: 18px; filter: drop-shadow(0 0 1px white); margin-left: -2px;"></i>
        </div>
        <span style="font-size: 13px; margin-left: 10px; font-weight: bold;">≥ 350 kW</span>
    </div>
    <hr style="margin: 12px 0; border-color: #bbb;">
    <strong style="font-size: 14px;">Status (Punkt):</strong><br>
    <div style="display: flex; align-items: center; margin-top: 10px;">
        <span style="color:#00FF00; font-size: 22px; width: 45px; text-align: center; line-height: 1;">●</span> 
        <span style="font-size: 13px; margin-left: 10px;">Betriebsbereit</span>
    </div>
    <div style="display: flex; align-items: center; margin-top: 5px;">
        <span style="color:#FF0000; font-size: 22px; width: 45px; text-align: center; line-height: 1;">●</span> 
        <span style="font-size: 13px; margin-left: 10px;">Belegt / Defekt</span>
    </div>
</div>
'''
st.sidebar.markdown(legende_html, unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.title("🔋 Reichweite")
battery = st.sidebar.slider("Batterie (kWh)", 10, 150, 75)
soc = st.sidebar.slider("Aktueller SOC (%)", 0, 100, 20)
cons = st.sidebar.slider("Verbrauch (kWh/100km)", 10.0, 40.0, 20.0, 0.5)
range_km = int((battery * (soc / 100)) / cons * 100)

# --- ZENTRUM ---
default_lat, default_lon = 50.1109, 8.6821 
target_lat, target_lon = None, None

if search_city:
    try:
        geo_url = f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}"
        geo_res = requests.get(geo_url, headers={'User-Agent': 'DC-Finder-App'}).json()
        if geo_res:
            target_lat, target_lon = float(geo_res[0]['lat']), float(geo_res[0]['lon'])
    except:
        st.sidebar.error("Stadt nicht gefunden.")

final_lat = target_lat if target_lat else (current_lat if current_lat else default_lat)
final_lon = target_lon if target_lon else (current_lon if current_lon else default_lon)

# --- KARTE ---
m = folium.Map(location=[final_lat, final_lon], zoom_start=11, tiles="cartodbpositron", zoom_control=False)

if current_lat and current_lon:
    folium.Marker([current_lat, current_lon], popup="Mein Standort", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
    folium.Circle([current_lat, current_lon], radius=range_km*1000, color="blue", fill=True, fill_opacity=0.05).add_to(m)

# --- DATEN LADEN (Exakt im Radius) ---
found_count = 0
if API_KEY:
    try:
        params = {
            "key": API_KEY, 
            "latitude": final_lat, 
            "longitude": final_lon, 
            "distance": range_km, # Hier wird jetzt wieder exakt nach Reichweite gefiltert
            "distanceunit": "KM", 
            "maxresults": 250, # Erhöht, damit nichts verschluckt wird
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
            
            # Erst hier filtern wir nach der eingestellten Mindestleistung
            if max_pwr < min_power: continue
            
            op_name = poi.get('OperatorInfo', {}).get('Title', "Unbekannt")
            if hide_tesla and "tesla" in op_name.lower(): continue
            
            s_id = int(poi.get('StatusTypeID', 0) or 0)
            s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"
            lat, lon = poi['AddressInfo']['Latitude'], poi['AddressInfo']['Longitude']
            
            g_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            a_maps = f"http://maps.apple.com/?daddr={lat},{lon}"
            
            pop_html = f'''<div style="width:200px; font-family:sans-serif; color:black;">
                            <div style="margin-bottom:5px;"><b style="font-size:18px;">{int(max_pwr)} kW</b> <span style="background:#eee; padding:2px 6px; border-radius:10px; font-size:12px;">{qty} 🔌</span></div>
                            <div style="font-size:12px; color:#666; margin-bottom:10px;">{op_name}</div>
                            <div style="display:flex; gap:5px;">
                                <a href="{g_maps}" target="_blank" style="flex:1; background:#4285F4; color:white; padding:8px; text-decoration:none; border-radius:5px; text-align:center; font-size:12px; font-weight:bold;">Google</a>
                                <a href="{a_maps}" target="_blank" style="flex:1; background:black; color:white; padding:8px; text-decoration:none; border-radius:5px; text-align:center; font-size:12px; font-weight:bold;">Apple</a>
                            </div></div>'''
            
            folium.Marker([lat, lon], icon=get_lightning_html(max_pwr, s_color), popup=folium.Popup(pop_html, max_width=250)).add_to(m)
            found_count += 1
    except: pass

if found_count > 0:
    st.markdown(f'<div class="found-badge">⚡ {found_count} Stationen</div>', unsafe_allow_html=True)

st_folium(m, height=800, width=None, key="dc_final_radius_fix", use_container_width=True)
