import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder Pro", layout="wide", page_icon="⚡")

def get_lightning_html(power_kw, status_color):
    # Logik für Blitze: Blau (50-199kW), Rot (200-300kW), Schwarz (>300kW)
    if 50 <= power_kw < 200:
        color, count = "blue", 1
    elif 200 <= power_kw <= 300:
        color, count = "red", 2
    else:
        color, count = "black", 3

    # Glow-Effekt nur bei echtem Status (Grün/Rot)
    glow = f"box-shadow: 0 0 10px {status_color}, 0 0 5px white;" if status_color in ["#00FF00", "#FF0000"] else ""
    
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 80px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 16px; height: 16px; margin-bottom: 2px; border: 2px solid white; {glow}"></div>
                    <div style="font-size: 24px; display: flex; justify-content: center; filter: drop-shadow(1px 1px 2px white);">{icons}</div>
                 </div>""",
        icon_size=(80, 50), icon_anchor=(40, 25)
    )

# --- SIDEBAR FILTER ---
st.sidebar.title("Filter & Optionen")
show_only_live = st.sidebar.checkbox("Nur mit Live-Status (Grün/Rot)", value=False)
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 350, 150)

st.title("⚡ EV Pro Finder")

API_KEY = st.secrets.get("OCM_API_KEY", None)
loc = get_geolocation()

if loc is not None:
    lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
    
    # Karte erstellen
    m = folium.Map(location=[lat, lon], zoom_start=12, tiles="cartodbpositron")
    folium.Marker([lat, lon], popup="Dein Standort", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)

    if API_KEY:
        # API Abfrage
        url = f"https://api.openchargemap.io/v3/poi/?key={API_KEY}&latitude={lat}&longitude={lon}&distance=40&countrycode=DE&maxresults=100"
        
        try:
            response = requests.get(url)
            data = response.json()

            for poi in data:
                try:
                    p_lat = poi['AddressInfo']['Latitude']
                    p_lon = poi['AddressInfo']['Longitude']
                    
                    # Höchste Leistung ermitteln
                    power = 0
                    if poi.get('Connections'):
                        power = max([c.get('PowerKW', 0) for c in poi['Connections'] if c.get('PowerKW') is not None], default=0)
                    
                    # Filter: Leistung
                    if power >= min_power:
                        
                        # Betreiber-Name bestimmen (Fallback-System)
                        if poi.get('OperatorInfo') and poi['OperatorInfo'].get('Title'):
                            betreiber = poi['OperatorInfo']['Title']
                        elif poi.get('AddressInfo') and poi['AddressInfo'].get('Title'):
                            betreiber = poi['AddressInfo']['Title']
                        else:
                            betreiber = "Schnellladestation"
                        
                        betreiber = betreiber.split('(')[0].strip()

                        # Status-Logik
                        status_id = int(poi.get('StatusTypeID', 0))
                        
                        if status_id in [10, 15]:
                            s_color, s_text = "#00FF00", "FREI"
                        elif status_id in [20, 30, 75]:
                            s_color, s_text = "#FF0000", "BELEGT"
                        elif status_id in [50, 100, 150, 200]:
                            s_color, s_text = "#FFA500", "DEFEKT"
                        else:
                            s_color, s_text = "#A9A9A9", "UNBEKANNT"

                        # Filter: Nur Live-Status anzeigen
                        if show_only_live and s_color not in ["#00FF00", "#FF0000"]:
                            continue

                        folium.Marker(
                            location=[p_lat, p_lon],
                            popup=f"<b>{betreiber}</b><br>Leistung: {power} kW<br>Status: {s_text}",
                            icon=get_lightning_html(power, s_color)
                        ).add_to(m)
                except:
                    continue
        except:
            st.error("Fehler beim Abrufen der Daten.")
    
    # Karte in Streamlit anzeigen
    st_folium(m, width="100%", height=650)
else:
    st.info("🌐 Suche Standort... Bitte Freigabe im Browser bestätigen.")
