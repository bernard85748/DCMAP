import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder", layout="wide", page_icon="⚡")

# --- API KEY CHECK ---
# Wir versuchen den Key zu laden, setzen ihn aber auf None, falls er fehlt
API_KEY = st.secrets.get("OCM_API_KEY", None)

# --- UI ---
st.title("⚡ EV Pro Finder (Vorschau)")

if not API_KEY:
    st.info("ℹ️ Die App läuft aktuell im **Vorschaumodus**, da noch kein API-Key hinterlegt wurde. Sobald du deinen Key in den Streamlit Secrets einträgst, erscheinen hier die Ladesäulen.")

# --- STANDORT & KARTE ---
loc = get_geolocation()

if loc is not None:
    try:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        
        # Basis-Karte erstellen
        m = folium.Map(location=[lat, lon], zoom_start=13, tiles="cartodbpositron")
        
        # Deinen Standort markieren
        folium.Marker(
            [lat, lon], 
            popup="Dein Standort", 
            icon=folium.Icon(color='gray', icon='user', prefix='fa')
        ).add_to(m)

        # Ladesäulen-Logik nur ausführen, wenn API_KEY vorhanden ist
        if API_KEY:
            try:
                url = f"https://api.openchargemap.io/v3/poi/?key={API_KEY}&latitude={lat}&longitude={lon}&distance=30"
                # ... (hier würde deine restliche Ladesäulen-Logik folgen)
            except Exception as e:
                st.error("Fehler bei der Datenabfrage.")
        
        # Karte anzeigen
        st_folium(m, width="100%", height=500)
        
    except KeyError:
        st.error("Standort konnte nicht ermittelt werden.")
else:
    st.warning("🌐 Bitte erlaube den Standortzugriff, um die Karte zu zentrieren.")
        st.error("Fehler beim Laden der Daten. Bitte API-Key prüfen.")
else:

    st.info("Bitte Standortzugriff im Browser erlauben...")
