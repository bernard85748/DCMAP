import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder DE", layout="wide", page_icon="⚡")

def get_lightning_html(power_kw, status_color):
    # Farblogik wie gewünscht
    if 50 <= power_kw < 200:
        color, count = "blue", 1
    elif 200 <= power_kw <= 300:
        color, count = "red", 2
    else:
        color, count = "black", 3

    # Wir machen den Status-Punkt etwas größer und fügen ein Glühen hinzu
    glow = f"box-shadow: 0 0 8px {status_color};" if status_color != "gray" else ""
    
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 80px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 14px; height: 14px; margin-bottom: 2px; border: 2px solid white; {glow}"></div>
                    <div style="font-size: 22px; display: flex; justify-content: center; filter: drop-shadow(1px 1px 1px white);">{icons}</div>
                 </div>""",
        icon_size=(80, 50), icon_anchor=(40, 25)
    )

st.title("⚡ EV Pro Finder (Live DE)")

API_KEY = st.secrets.get("OCM_API_KEY", None)

# --- STANDORT-ABFRAGE ---
loc = get_geolocation()

if loc is not None:
    lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
    
    m = folium.Map(location=[lat, lon], zoom_start=12, tiles="cartodbpositron")
    folium.Marker([lat, lon], popup="Dein Standort", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)

    if API_KEY:
        # Wir rufen zusätzliche Status-Felder ab
        url = f"https://api.openchargemap.io/v3/poi/?key={API_KEY}&latitude={lat}&longitude={lon}&distance=50&countrycode=DE&maxresults=100"
        
        try:
            data = requests.get(url).json()

            for poi in data:
                p_lat = poi['AddressInfo']['Latitude']
                p_lon = poi['AddressInfo']['Longitude']
                power = poi['Connections'][0].get('PowerKW', 0) if poi['Connections'] else 0
                
                if power >= 50:
                    # Erweiterte Status-Logik für deutsche Stationen
                    status_id = poi.get('StatusTypeID', 0)
                    
                    # 10=Verfügbar, 20=Belegt, 30=Belegt, 50=Defekt, 75=In Benutzung
                    if status_id == 10:
                        s_color = "#00ff00" # Leuchtendes Grün
                    elif status_id in [20, 30, 75]:
                        s_color = "#ff0000" # Signalrot
                    elif status_id in [50, 100, 150]:
                        s_color = "#ffae00" # Orange (Defekt)
                    else:
                        s_color = "gray" # Unbekannt
                    
                    # Info-Text für das Popup
                    betreiber = poi['ServiceProvider'].get('Title', 'Unbekannter Betreiber') if poi.get('ServiceProvider') else "Privat/Unbekannt"
                    
                    folium.Marker(
                        location=[p_lat, p_lon],
                        popup=folium.Popup(f"<b>{betreiber}</b><br>Leistung: {power}kW<br>Status: {'Frei' if s_color=='#00ff00' else 'Belegt/Unbekannt'}", max_width=200),
                        icon=get_lightning_html(power, s_color)
                    ).add_to(m)
        except Exception as e:
            st.error(f"Datenfehler: {e}")
    
    st_folium(m, width="100%", height=600)
else:
    st.info("🌐 Bitte Standortzugriff erlauben...")
