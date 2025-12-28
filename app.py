import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder", layout="wide", page_icon="⚡")

# Hilfsfunktion für die Blitz-Symbole (Blau/Rot/Schwarz)
def get_lightning_html(power_kw, status_color):
    if 50 <= power_kw < 200:
        color, count = "blue", 1
    elif 200 <= power_kw <= 300:
        color, count = "red", 2
    else:
        color, count = "black", 3

    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 60px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 10px; height: 10px; margin-bottom: 2px; border: 1px solid white; box-shadow: 0px 0px 3px black;"></div>
                    <div style="font-size: 20px; display: flex; justify-content: center;">{icons}</div>
                 </div>""",
        icon_size=(60, 40), icon_anchor=(30, 20)
    )

st.title("⚡ EV Pro Finder")

# API Key aus den Secrets laden
API_KEY = st.secrets.get("OCM_API_KEY", None)

if not API_KEY:
    st.warning("⚠️ Bitte trage deinen OCM_API_KEY in den Streamlit Settings ein!")

# --- STANDORT-ABFRAGE ---
loc = get_geolocation()

if loc is not None:
    try:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        
        m = folium.Map(location=[lat, lon], zoom_start=12, tiles="cartodbpositron")
        folium.Marker([lat, lon], popup="Dein Standort", icon=folium.Icon(color='gray', icon='user', prefix='fa')).add_to(m)

        # Ladesäulen abrufen, wenn Key vorhanden
        if API_KEY:
            url = f"https://api.openchargemap.io/v3/poi/?key={API_KEY}&latitude={lat}&longitude={lon}&distance=50&maxresults=50"
            response = requests.get(url)
            data = response.json()

            for poi in data:
                try:
                    p_lat = poi['AddressInfo']['Latitude']
                    p_lon = poi['AddressInfo']['Longitude']
                    # Leistung der ersten Steckdose nehmen
                    power = poi['Connections'][0].get('PowerKW', 0) if poi['Connections'] else 0
                    
                    if power >= 50: # Nur Schnelllader anzeigen
                        # Status-Farbe bestimmen
                        status_id = poi.get('StatusTypeID', 0)
                        s_color = "green" if status_id == 10 else ("red" if status_id in [20, 30] else "gray")
                        
                        folium.Marker(
                            location=[p_lat, p_lon],
                            popup=f"<b>{poi['AddressInfo']['Title']}</b><br>Leistung: {power}kW",
                            icon=get_lightning_html(power, s_color)
                        ).add_to(m)
                except:
                    continue
        
        st_folium(m, width="100%", height=600)
        
    except Exception as e:
        st.error(f"Fehler: {e}")
else:
    st.info("🌐 Warte auf Standortfreigabe...")
