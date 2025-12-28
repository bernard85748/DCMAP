import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- KONFIGURATION & DESIGN ---
st.set_page_config(page_title="EV Ultra Finder", layout="wide", page_icon="⚡")

# CSS für die Legende und das Styling
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stSidebar { background-color: #ffffff; border-right: 1px solid #ddd; }
    </style>
    """, unsafe_allow_BIT_OR_double_quote=True)

# Hilfsfunktion für die Blitz-Symbole
def get_lightning_html(power_kw, status_color):
    if 50 <= power_kw < 200:
        color, count = "blue", 1
    elif 200 <= power_kw <= 300:
        color, count = "red", 2
    else:
        color, count = "black", 3

    # HTML für Blitze + Status-Kreis
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 60px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 10px; height: 10px; margin-bottom: 2px; border: 1px solid white;"></div>
                    <div style="font-size: 20px; display: flex; justify-content: center;">{icons}</div>
                 </div>""",
        icon_size=(60, 40), icon_anchor=(30, 20)
    )

# --- SIDEBAR: FILTER & LEGENDE ---
st.sidebar.title("⚡ EV Pro Filter")
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 400, 150)
st.sidebar.markdown("---")
st.sidebar.subheader("🗺️ Legende")
st.sidebar.markdown("🔵 ⚡ **50-200kW**: Blau")
st.sidebar.markdown("🔴 ⚡⚡ **200-300kW**: Rot")
st.sidebar.markdown("⚫ ⚡⚡⚡ **>300kW**: Schwarz")
st.sidebar.markdown("---")
st.sidebar.markdown("🟢 Verfügbar | 🔴 Belegt | ⚪ Unbekannt")

# --- HAUPTLOGIK ---
loc = get_geolocation()

if loc:
    lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
    
    # API Abfrage (Beispiel Open Charge Map)
    # Hier nutzt du deinen Key aus den Streamlit Secrets
    API_KEY = st.secrets.get("OCM_API_KEY", "DEMO_KEY") 
    url = f"https://api.openchargemap.io/v3/poi/?key={API_KEY}&latitude={lat}&longitude={lon}&distance=50&minpowerkw={min_power}"
    
    try:
        data = requests.get(url).json()
        m = folium.Map(location=[lat, lon], zoom_start=12, tiles="cartodbpositron")
        
        # User Standort
        folium.Marker([lat, lon], popup="Du bist hier", icon=folium.Icon(color='gray', icon='user', prefix='fa')).add_to(m)

        for poi in data:
            p_lat = poi['AddressInfo']['Latitude']
            p_lon = poi['AddressInfo']['Longitude']
            power = poi['Connections'][0].get('PowerKW', 0)
            
            # Status-Logik (vereinfacht)
            status_id = poi.get('StatusTypeID', 0)
            status_color = "green" if status_id == 10 else ("red" if status_id in [20, 30] else "gray")
            
            folium.Marker(
                location=[p_lat, p_lon],
                popup=f"<b>{poi['AddressInfo']['Title']}</b><br>Leistung: {power}kW",
                icon=get_lightning_html(power, status_color)
            ).add_to(m)

        st_folium(m, width="100%", height=600)
    except:
        st.error("Fehler beim Laden der Daten. Bitte API-Key prüfen.")
else:
    st.info("Bitte Standortzugriff im Browser erlauben...")