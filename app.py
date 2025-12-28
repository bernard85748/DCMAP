import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder Pro", layout="wide", page_icon="⚡")

# API KEY aus den Secrets laden
API_KEY = st.secrets.get("OCM_API_KEY", None)

def get_lightning_html(power_kw, status_color):
    """Erzeugt die Blitz-Icons basierend auf der Leistung."""
    color = "blue" if power_kw < 200 else "red" if power_kw <= 300 else "black"
    count = 1 if power_kw < 200 else 2 if power_kw <= 300 else 3
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 60px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 12px; height: 12px; border: 2px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.3);"></div>
                    <div style="font-size: 20px; display: flex; justify-content: center; filter: drop-shadow(1px 1px 1px white);">{icons}</div>
                 </div>""",
        icon_size=(60, 40), icon_anchor=(30, 20)
    )

# --- SIDEBAR: REICHWEITE & FILTER ---
st.sidebar.title("🌍 Reiseplanung")
search_city = st.sidebar.text_input("Stadt suchen", key="city_input")

st.sidebar.divider()
st.sidebar.title("🔋 Reichweite")
battery = st.sidebar.number_input("Batterie (kWh)", 10, 150, 75, step=1)
soc = st.sidebar.slider("Akku %", 0, 100, 40)
cons = st.sidebar.number_input("Verbrauch (kWh/100km)", 10, 40, 20, step=1)
range_km = int((battery * (soc / 100)) / cons * 100)
st.sidebar.metric("Reichweite", f"{range_km} km")

st.sidebar.divider()
st.sidebar.title("⚙️ Filter")
only_tesla = st.sidebar.checkbox("Nur Tesla Supercharger", key="tesla_check")
country_options = {"Deutschland": "DE", "Frankreich": "FR", "Österreich": "AT", "Schweiz": "CH", "Italien": "IT"}
selected_countries = st.sidebar.multiselect("Länder", options=list(country_options.keys()), default=["Deutschland"])
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 350, 150)
search_radius = st.sidebar.slider("Suchradius (km)", 10, 500, 150)

if st.sidebar.button("🔄 Filter zurücksetzen"):
    for key in ["city_input", "tesla_check"]:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- STANDORT FINDEN ---
target_lat, target_lon = None, None

if search_city:
    try:
        geo = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}", headers={'User-Agent': 'EV-Finder-V3'}).json()
        if geo:
            target_lat, target_lon = float(geo[0]['lat']), float(geo[0]['lon'])
    except:
        st.error("Fehler bei der Stadtsuche.")
else:
    # GPS Fallback
    loc = get_geolocation()
    if loc:
        target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

# --- KARTE ---
st.title("⚡ EV Ultra Finder Pro")

if target_lat and target_lon:
    m = folium.Map(location=[target_lat, target_lon], zoom_start=8, tiles="cartodbpositron")
    
    # Reichweitenkreis zeichnen
    folium.Circle(
        [target_lat, target_lon],
        radius=range_km * 1000,
        color="green",
        fill=True,
        fill_opacity=0.1
    ).add_to(m)

    if API_KEY:
        c_codes = [country_options[c] for c in selected_countries]
        params = {
            "key": API_KEY,
            "latitude": target_lat,
            "longitude": target_lon,
            "distance": search_radius,
            "compact": "true",
            "verbose": "false",
            "countrycode": ",".join(c_codes)
        }
        
        try:
            response = requests.get("https://api.openchargemap.io/v3/poi/", params=params)
            if response.status_code == 200:
                data = response.json()
                found_count = 0
                for poi in data:
                    # Leistung & Anbieter-Filter
                    conns = poi.get('Connections', [])
                    pwr = max([c.get('PowerKW', 0) for c in conns if c.get('PowerKW')], default=0)
                    if pwr < min_power: continue
                    
                    op = poi.get('OperatorInfo', {}).get('Title', 'Unbekannt')
                    if only_tesla and "tesla" not in op.lower(): continue

                    # Status & Farbe
                    s_id = int(poi.get('StatusTypeID', 0))
                    s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"
                    
                    # Marker hinzufügen
                    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={poi['AddressInfo']['Latitude']},{poi['AddressInfo']['Longitude']}"
                    pop_html = f"<b>{op}</b><br>{int(pwr)} kW<br><a href='{nav_url}' target='_blank'>📍 Navigation</a>"
                    
                    folium.Marker(
                        [poi['AddressInfo']['Latitude'], poi['AddressInfo']['Longitude']],
                        popup=folium.Popup(pop_html, max_width=200),
                        icon=get_lightning_html(pwr, s_color)
                    ).add_to(m)
                    found_count += 1
                
                st.sidebar.write(f"✅ {found_count} Ladestationen gefunden.")
            else:
                st.error("API-Key ungültig oder Limit erreicht.")
        except Exception as e:
            st.warning("Konnte Ladestationen nicht laden.")
    else:
        st.warning("⚠️ Kein API-Key in den Secrets gefunden.")

    st_folium(m, width="100%", height=600, key="final_map")
else:
    st.info("Bitte Stadt eingeben oder GPS-Standort freigeben.")
