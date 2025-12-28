import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder", layout="wide", page_icon="⚡")

# --- API KEY CHECK ---
API_KEY = st.secrets.get("OCM_API_KEY", None)

st.title("⚡ EV Pro Finder (Vorschau)")

if not API_KEY:
    st.info("ℹ️ Die App läuft im Sicherheits-Modus. Sobald du deinen API-Key in Streamlit einträgst, erscheinen die Ladesäulen.")

# --- STANDORT-ABFRAGE ---
loc = get_geolocation()

if loc is not None:
    try:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        
        # Karte erstellen
        m = folium.Map(location=[lat, lon], zoom_start=13, tiles="cartodbpositron")
        
        # Standort markieren
        folium.Marker(
            [lat, lon], 
            popup="Dein Standort", 
            icon=folium.Icon(color='gray', icon='user', prefix='fa')
        ).add_to(m)

        # Ladesäulen laden (nur wenn Key da ist)
        if API_KEY:
            try:
                url = f"https://api.openchargemap.io/v3/poi/?key={API_KEY}&latitude={lat}&longitude={lon}&distance=30"
                # Hier käme die weitere Logik
            except Exception as e:
                st.error("Fehler beim Laden der Daten. Bitte API-Key prüfen.")
        
        # Karte anzeigen
        st_folium(m, width="100%", height=500)
        
    except Exception as e:
        st.error(f"Ein Fehler ist aufgetreten: {e}")
else:
    st.warning("🌐 Bitte erlaube den Standortzugriff im Browser.")
