import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from folium.features import DivIcon

# --- SETUP ---
st.set_page_config(page_title="EV Ultra Finder Pro", layout="wide", page_icon="⚡")

# 1. FUNKTION FÜR ICONS & STATUS
def get_lightning_html(power_kw, status_color):
    color = "blue" if power_kw < 200 else "red" if power_kw <= 300 else "black"
    count = 1 if power_kw < 200 else 2 if power_kw <= 300 else 3
    icons = "".join([f'<i class="fa fa-bolt" style="color:{color}; margin: 1px;"></i>' for _ in range(count)])
    
    # Glow-Effekt für besseren Kontrast
    glow = f"box-shadow: 0 0 8px {status_color};" if status_color != "#A9A9A9" else ""
    
    return DivIcon(
        html=f"""<div style="display: flex; flex-direction: column; align-items: center; width: 60px;">
                    <div style="background-color: {status_color}; border-radius: 50%; width: 12px; height: 12px; border: 2px solid white; {glow}"></div>
                    <div style="font-size: 20px; display: flex; justify-content: center; filter: drop-shadow(1px 1px 1px white);">{icons}</div>
                 </div>""",
        icon_size=(60, 40), icon_anchor=(30, 20)
    )

# --- SIDEBAR ---
st.sidebar.title("🌍 Reiseplanung")
search_city = st.sidebar.text_input("Stadt suchen", key="city_input")

st.sidebar.divider()
st.sidebar.title("🔋 Reichweite")
# Ganzzahlen ohne Komma
battery = st.sidebar.number_input("Batterie (kWh)", 10, 150, 75, step=1)
soc = st.sidebar.slider("Akku %", 0, 100, 40)
cons = st.sidebar.number_input("Verbrauch (kWh/100km)", 10, 40, 20, step=1)
range_km = int((battery * (soc / 100)) / cons * 100)
st.sidebar.metric("Reichweite", f"{range_km} km")

st.sidebar.divider()
st.sidebar.title("⚙️ Filter")
only_tesla = st.sidebar.checkbox("Nur Tesla Supercharger", key="tesla_check")
country_options = {"Deutschland": "DE", "Frankreich": "FR", "Österreich": "AT", "Schweiz": "CH"}
selected_countries = st.sidebar.multiselect("Länder", options=list(country_options.keys()), default=["Deutschland"], key="countries_ms")
min_power = st.sidebar.slider("Mindestleistung (kW)", 50, 350, 150, key="power_slider")
search_radius = st.sidebar.slider("Radius (km)", 10, 500, 150)

if st.sidebar.button("🔄 Alle Filter zurücksetzen"):
    for key in ["city_input", "countries_ms", "power_slider", "tesla_check"]:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

# --- HAUPTTEIL ---
st.title("⚡ EV Ultra Finder Pro")
API_KEY = st.secrets.get("OCM_API_KEY", None)

target_lat, target_lon = None, None
if search_city:
    try:
        geo = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={search_city}", headers={'User-Agent': 'EV-App'}).json()
        if geo: target_lat, target_lon = float(geo[0]['lat']), float(geo[0]['lon'])
    except: st.error("Suche fehlgeschlagen.")
else:
    loc = get_geolocation()
    if loc: target_lat, target_lon = loc['coords']['latitude'], loc['coords']['longitude']

if target_lat and target_lon:
    m = folium.Map(location=[target_lat, target_lon], zoom_start=8, tiles="cartodbpositron")
    folium.Circle([target_lat, target_lon], radius=range_km*1000, color="green", fill=True, fill_opacity=0.1).add_to(m)

    all_stations = []

    if API_KEY:
        # 1. Open Charge Map
        c_codes = [country_options[c] for c in selected_countries]
        params = {"key": API_KEY, "latitude": target_lat, "longitude": target_lon, "distance": search_radius, "compact": "true", "countrycode": ",".join(c_codes)}
        try:
            ocm_data = requests.get("https://api.openchargemap.io/v3/poi/", params=params).json()
            for poi in ocm_data:
                pwr = max([c.get('PowerKW', 0) for c in poi.get('Connections', []) if c.get('PowerKW')], default=0)
                s_id = int(poi.get('StatusTypeID', 0))
                # Status-Farbe
                s_color = "#00FF00" if s_id in [10, 15, 50] else "#FF0000" if s_id in [20, 30, 75] else "#A9A9A9"
                
                all_stations.append({
                    'lat': poi['AddressInfo']['Latitude'], 'lon': poi['AddressInfo']['Longitude'],
                    'power': int(pwr), 'op': poi.get('OperatorInfo', {}).get('Title', 'Unbekannt'),
                    'color': s_color, 'source': 'OCM'
                })
        except: st.warning("Fehler beim Laden von OCM.")

        # 2. NAP Frankreich (falls ausgewählt)
        if "Frankreich" in selected_countries:
            try:
                fr_url = f"https://opendata.agence-recharge-vehicule-electrique.fr/api/records/1.0/search/?dataset=irve-0&geofilter.distance={target_lat},{target_lon},{search_radius*1000}&rows=50"
                fr_res = requests.get(fr_url).json()
                for rec in fr_res.get('records', []):
                    f = rec['fields']
                    all_stations.append({
                        'lat': f['geo_point_2d'][0], 'lon': f['geo_point_2d'][1],
                        'power': int(f.get('puissance_nominale', 0)), 'op': f.get('nom_enseigne', 'NAP-FR'),
                        'color': "#A9A9A9", 'source': 'NAP-FR'
                    })
            except: pass

    # MARKER ZEICHNEN
    found_count = 0
    for s in all_stations:
        if s['power'] < min_power: continue
        if only_tesla and "tesla" not in s['op'].lower(): continue

        nav_url = f"https://www.google.com/maps/dir/?api=1&destination={s['lat']},{s['lon']}"
        pop_html = f"<b>{s['op']}</b><br>{s['power']} kW<br><small>{s['source']}</small><br><a href='{nav_url}' target='_blank'>📍 Navigation</a>"
        
        folium.Marker(
            [s['lat'], s['lon']], 
            popup=folium.Popup(pop_html, max_width=200),
            icon=get_lightning_html(s['power'], s['color'])
        ).add_to(m)
        found_count += 1

    st.sidebar.write(f"✅ {found_count} Ladeparks gefunden.")
    st_folium(m, width="100%", height=600, key="map_v3")
else:
    st.info("Bitte Stadt suchen oder GPS freigeben.")
