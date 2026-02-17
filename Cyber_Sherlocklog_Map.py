import streamlit as st
import plotly.graph_objects as go
import re
import pandas as pd
from PIL import Image
from datetime import datetime

# --- 1. CONFIGURATION & LOCKED CALIBRATION ---
st.set_page_config(layout="wide", page_title="DayZ Intel Mapper")

# 🔒 HARDCODED "WINNING" SETTINGS (No Menus, No Sliders)
LOCKED_SETTINGS = {
    "img_off_x": 127,
    "img_off_y": 628,
    "img_scale": 1.04,
    "img_opacity": 1.0,
    "log_off_x": 150,
    "log_off_y": 40,
    "log_format": "Format: <X, Y, Z>",
    "swap_xy": False,
    "show_grid": True,
    "show_towns": True
}

MAP_CONFIG = {
    "Chernarus": {"size": 15360, "image": "map_chernarus.png"}, 
    "Livonia": {"size": 12800, "image": "map_livonia.png"},
    "Sakhal": {"size": 8192, "image": "map_sakhal.png"}
}

# --- DATABASE (Updated with User Coordinates) ---
TOWN_DATA = {
    "Chernarus": [
        # --- New/Updated User Entries ---
        {"name": "Vybor", "x": 3916, "y": 8889}, # Updated
        {"name": "Verbnik", "x": 4416, "y": 9100},
        {"name": "Dubnik", "x": 3300, "y": 10333},
        {"name": "Lopatino", "x": 2796, "y": 10026}, # Updated
        {"name": "Vavilovo", "x": 2335, "y": 11097},
        {"name": "Kalinka", "x": 2335, "y": 11097},
        {"name": "Bashnya", "x": 2335, "y": 11097},
        {"name": "Adamovka", "x": 5340, "y": 11380},
        {"name": "Bogat", "x": 7056, "y": 12021},

        # --- Major Cities ---
        {"name": "Chernogorsk", "x": 6600, "y": 2500},
        {"name": "Elektrozavodsk", "x": 10200, "y": 2300},
        {"name": "Berezino", "x": 12300, "y": 9500},
        {"name": "Severograd", "x": 8400, "y": 13600},
        {"name": "Novodmitrovsk", "x": 11500, "y": 14300},
        {"name": "Zelenogorsk", "x": 2700, "y": 5300},
        {"name": "Novaya Petrovka", "x": 3500, "y": 12400},
        {"name": "Svetlojarsk", "x": 13900, "y": 13300},

        # --- Mid-Tier Towns ---
        {"name": "Balota", "x": 4600, "y": 2500},
        {"name": "Kamenka", "x": 1800, "y": 2200},
        {"name": "Komarovo", "x": 3600, "y": 2400},
        {"name": "Pavlovo", "x": 1600, "y": 3800},
        {"name": "Kozlovka", "x": 4400, "y": 4600},
        {"name": "Mogilevka", "x": 7500, "y": 5100},
        {"name": "Nadezhdino", "x": 5800, "y": 4700},
        {"name": "Staroye", "x": 10100, "y": 5500},
        {"name": "Gorka", "x": 9500, "y": 8800},
        {"name": "Novy Sobor", "x": 7100, "y": 7700},
        {"name": "Stary Sobor", "x": 6000, "y": 7700},
        {"name": "Kabanino", "x": 5300, "y": 8600},
        {"name": "Grishino", "x": 5900, "y": 10300},
        {"name": "Krasnostav", "x": 11100, "y": 12300},
        {"name": "Solnichniy", "x": 13300, "y": 6200},
        {"name": "Nizhnoye", "x": 13000, "y": 8200},
        {"name": "Kamyshovo", "x": 12000, "y": 3500},

        # --- Villages & Small Settlements ---
        {"name": "Berezhki", "x": 13500, "y": 14500},
        {"name": "Black Lake", "x": 13300, "y": 11500},
        {"name": "Bor", "x": 3300, "y": 3900},
        {"name": "Dolina", "x": 11200, "y": 6500},
        {"name": "Drozhino", "x": 3400, "y": 4800},
        {"name": "Dubrovka", "x": 10400, "y": 9800},
        {"name": "Guglovo", "x": 8500, "y": 6600},
        {"name": "Gvozdno", "x": 8600, "y": 11900},
        {"name": "Khelm", "x": 12300, "y": 10800},
        {"name": "Msta", "x": 11200, "y": 5400},
        {"name": "Myshkino", "x": 2000, "y": 8000},
        {"name": "Olsha", "x": 13300, "y": 12800},
        {"name": "Orlovets", "x": 12100, "y": 7200},
        {"name": "Petrovka", "x": 5000, "y": 12500},
        {"name": "Pogorevka", "x": 4600, "y": 6500},
        {"name": "Polana", "x": 10700, "y": 8100},
        {"name": "Prigorodki", "x": 7800, "y": 3200},
        {"name": "Pulkovo", "x": 4900, "y": 5600},
        {"name": "Pusta", "x": 9100, "y": 3900},
        {"name": "Pustoshka", "x": 3000, "y": 9600},
        {"name": "Ratnoe", "x": 5800, "y": 13400},
        {"name": "Rogovo", "x": 4700, "y": 8500},
        {"name": "Shakhovka", "x": 9600, "y": 6500},
        {"name": "Sinystok", "x": 1300, "y": 12100},
        {"name": "Sosnovka", "x": 2500, "y": 6400},
        {"name": "Topolniki", "x": 14300, "y": 10800},
        {"name": "Tisy (Town)", "x": 1600, "y": 13700},
        {"name": "Tulga", "x": 12800, "y": 4400},
        {"name": "Vyshnoye", "x": 6600, "y": 6100},
        {"name": "Vysotovo", "x": 6000, "y": 2700}
    ],
    "Livonia": [
        {"name": "Topolin", "x": 6200, "y": 11000},
        {"name": "Brena", "x": 6300, "y": 11800},
        {"name": "Nadbor", "x": 5600, "y": 4500},
        {"name": "Sitnik", "x": 6300, "y": 2200},
        {"name": "Radunin", "x": 9500, "y": 6800}
    ],
    "Sakhal": []
}

DEFAULT_POI_DATABASE = {
    "Chernarus": {
        # --- Key Military & Landmarks ---
        "🛡️ Military": [
            {"name": "NWAF", "x": 4600, "y": 10400},
            {"name": "Tisy Military Base", "x": 1600, "y": 14000},
            {"name": "Troitskoe Military", "x": 7200, "y": 14600},
            {"name": "Kamensk Military", "x": 7800, "y": 12800},
            {"name": "Myshkino Tents", "x": 1000, "y": 7500},
            {"name": "MB VMC", "x": 4497, "y": 8284}, # New User Entry
        ],
        "🏰 Landmarks": [
            {"name": "Green Mountain", "x": 3700, "y": 5900},
            {"name": "Altar", "x": 8100, "y": 9100},
            {"name": "Devil's Castle", "x": 6886, "y": 11494} # Updated User Entry
        ]
    }
}

# --- 2. HELPERS ---
@st.cache_resource
def load_map_image(image_path):
    try:
        return Image.open(image_path)
    except Exception:
        return None

@st.cache_data
def parse_log_file_content(content_bytes):
    logs = []
    content = content_bytes.decode("utf-8", errors='ignore')
    lines = content.split('\n')
    
    coord_pattern = re.compile(r"<([0-9\.-]+),\s*([0-9\.-]+),\s*([0-9\.-]+)>")
    name_pattern = re.compile(r'(?:Player|Identity)\s+"([^"]+)"')
    datetime_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})')
    time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2})')

    for line in lines:
        coord_match = coord_pattern.search(line)
        if coord_match:
            v1, v2, v3 = coord_match.groups()
            name_match = name_pattern.search(line)
            
            dt_match = datetime_pattern.search(line)
            t_match = time_pattern.search(line)
            
            if dt_match:
                time_str = dt_match.group(1)
                try: log_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                except: log_time = None
            elif t_match:
                time_str = t_match.group(1)
                try: log_time = datetime.strptime(time_str, "%H:%M:%S")
                except: log_time = None
            else:
                time_str = "Unknown Time"
                log_time = None

            name = name_match.group(1) if name_match else "Unknown"
            
            content_lower = line.lower()
            is_hit = any(x in content_lower for x in ['hit', 'damage', 'shot', 'killed', 'unconscious'])
            icon = "💥" if is_hit else "👤"
            
            logs.append({
                "time_obj": log_time,
                "time_str": time_str,
                "name": name,
                "icon": icon,
                "raw_1": float(v1),
                "raw_2": float(v2),
                "raw_3": float(v3)
            })
    return pd.DataFrame(logs)

@st.cache_data
def parse_poi_csv(uploaded_csv):
    try:
        df = pd.read_csv(uploaded_csv)
        new_db = {}
        for _, row in df.iterrows():
            m_name = row['map']
            cat = row['category']
            if m_name not in new_db: new_db[m_name] = {}
            if cat not in new_db[m_name]: new_db[m_name][cat] = []
            new_db[m_name][cat].append({"name": row['name'], "x": float(row['x']), "y": float(row['y'])})
        return new_db
    except Exception:
        return DEFAULT_POI_DATABASE

# --- 3. COORDINATE MATH ---
def transform_coords(game_x, game_y, settings):
    return game_x, game_y

# --- 4. RENDER ENGINE ---
def render_map(df, map_name, settings, search_term, active_layers, poi_db):
    config = MAP_CONFIG[map_name]
    map_size = config["size"]
    fig = go.Figure()

    # A. IMAGE LAYER
    img = load_map_image(config["image"])
    if img:
        img_width = map_size * settings['img_scale']
        img_height = map_size * settings['img_scale']
        img_x = settings['img_off_x']
        img_y = map_size + settings['img_off_y'] 
        
        fig.add_layout_image(
            dict(
                source=img, xref="x", yref="y",
                x=img_x, y=img_y,
                sizex=img_width, sizey=img_height,
                sizing="stretch", opacity=settings['img_opacity'],
                layer="below"
            )
        )
    else:
        fig.add_shape(type="rect", x0=0, y0=0, x1=map_size, y1=map_size, line=dict(color="RoyalBlue"))

    # B. PHYSICAL GRID
    if settings['show_grid']:
        grid_x, grid_y = [], []
        for i in range(16): 
            pos = i * 1000
            grid_x.extend([pos, pos, None]) 
            grid_y.extend([0, map_size, None])
        for i in range(16): 
            pos = i * 1000
            grid_x.extend([0, map_size, None]) 
            grid_y.extend([pos, pos, None])

        fig.add_trace(go.Scatter(
            x=grid_x, y=grid_y, mode='lines',
            line=dict(color='rgba(255, 255, 255, 0.2)', width=1),
            hoverinfo='skip', name='Grid'
        ))

    # C. TOWNS & POIS
    if settings['show_towns'] and map_name in TOWN_DATA:
        t_x, t_y, t_names = [], [], []
        for town in TOWN_DATA[map_name]:
            t_x.append(town['x'])
            t_y.append(town['y'])
            t_names.append(town['name'])
        
        fig.add_trace(go.Scatter(
            x=t_x, y=t_y, mode='markers+text', text=t_names, textposition="top center",
            marker=dict(size=6, color='yellow', line=dict(width=1, color='black')),
            textfont=dict(family="Arial Black", size=14, color="black"), 
            hovertemplate="<b>%{text}</b><br>Game: %{x:.0f} / %{y:.0f}<extra></extra>",
            name="Towns"
        ))

    if map_name in poi_db:
        for layer_name, locations in poi_db[map_name].items():
            if layer_name in active_layers:
                l_x, l_y, l_txt = [], [], []
                for loc in locations:
                    tx, ty = transform_coords(loc['x'], loc['y'], settings)
                    l_x.append(tx); l_y.append(ty); l_txt.append(loc['name'])
                
                color = "cyan"
                if "Military" in layer_name: color = "red"
                elif "Castle" in layer_name: color = "purple"
                
                fig.add_trace(go.Scatter(
                    x=l_x, y=l_y, mode='markers',
                    marker=dict(size=9, color=color, symbol='diamond', line=dict(width=1, color='black')),
                    text=l_txt, name=layer_name, 
                    hovertemplate="<b>%{text}</b><br>Game: %{x:.0f} / %{y:.0f}<extra></extra>"
                ))

    # D. PLAYERS (LOGS)
    if not df.empty:
        raw_x = df["raw_1"]
        raw_y = df["raw_2"] # LOCKED to Format <X, Y, Z>
        
        fx = raw_x + settings['log_off_x']
        fy = raw_y + settings['log_off_y']
        
        if search_term:
            df['filtered'] = df['name'].str.contains(search_term, case=False, na=False)
            df_plot = df[df['filtered']].copy()
            if not df_plot.empty:
                p_x = df_plot["raw_1"]
                p_y = df_plot["raw_2"]
                p_fx = p_x + settings['log_off_x']
                p_fy = p_y + settings['log_off_y']
                
                adm_x = df_plot["raw_1"]
                adm_y = p_y
                
                fig.add_trace(go.Scatter(
                    x=p_fx, y=p_fy, mode='text',
                    text=df_plot["icon"],
                    textfont=dict(size=14),
                    customdata=list(zip(df_plot["time_str"], df_plot["name"], adm_x, adm_y)),
                    hovertemplate="<b>%{customdata[0]}</b><br>Player: %{customdata[1]}<br>ADM: %{customdata[2]:.1f} / %{customdata[3]:.1f}<extra></extra>",
                    name="Logs"
                ))
        else:
            fig.add_trace(go.Scatter(
                x=fx, y=fy, mode='text',
                text=df["icon"],
                textfont=dict(size=14),
                customdata=list(zip(df["time_str"], df["name"], raw_x, raw_y)),
                hovertemplate="<b>%{customdata[0]}</b><br>Player: %{customdata[1]}<br>ADM: %{customdata[2]:.1f} / %{customdata[3]:.1f}<extra></extra>",
                name="Logs"
            ))

    # E. RULERS
    grid_vals_x, grid_text_x = [], []
    for i in range(16): 
        grid_vals_x.append(i * 1000); grid_text_x.append(f"{i:02d}")
    grid_vals_y, grid_text_y = [], []
    for i in range(16): 
        grid_vals_y.append(i * 1000); grid_text_y.append(f"{15-i:02d}")

    # F. LAYOUT (Optimized margins & Click disabled)
    fig.update_layout(
        height=900,
        margin={"l": 40, "r": 40, "t": 80, "b": 40}, 
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        dragmode="pan", 
        hovermode="closest", showlegend=True,
        legend=dict(yanchor="bottom", y=0.01, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0.6)", font=dict(color="white")),
        
        xaxis=dict(
            visible=True, range=[0, map_size], side="top",
            showgrid=False, gridcolor="rgba(0,0,0,0)", 
            tickmode="array", tickvals=grid_vals_x, ticktext=grid_text_x,
            tickfont=dict(color="white", size=14, family="Arial Black"), zeroline=False
        ),

        yaxis=dict(
            visible=True, range=[0, map_size], side="left",
            showgrid=False, gridcolor="rgba(0,0,0,0)",
            tickmode="array", tickvals=grid_vals_y, ticktext=grid_text_y,
            tickfont=dict(color="white", size=14, family="Arial Black"),
            scaleanchor="x", scaleratio=1, zeroline=False
        )
    )
    return fig, map_size

# --- 5. UI MAIN ---
def main():
    st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        [data-testid="stSidebar"] { background-color: #262730; }
        header[data-testid="stHeader"] { display: none !important; }
        #MainMenu { display: none !important; }
        footer { display: none !important; }
        [data-testid="stDecoration"] { display: none !important; }
        .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🗺️ Intel Control")
        selected_map = st.selectbox("Map", list(MAP_CONFIG.keys()))
        st.write("---")
        uploaded_log = st.file_uploader("1. Upload Logs", type=['adm', 'rpt', 'log'])
        st.caption("ℹ️ **Upload POI DB**: Optional CSV for permanent bases/traders.")
        uploaded_csv = st.file_uploader("2. Upload POI DB", type=['csv'])
        
        if uploaded_csv:
            current_db = parse_poi_csv(uploaded_csv)
            st.success("✅ DB Loaded")
        else:
            current_db = DEFAULT_POI_DATABASE

        df = parse_log_file_content(uploaded_log.getvalue()) if uploaded_log else pd.DataFrame()

        if not df.empty and 'time_obj' in df.columns:
            valid_times = df.dropna(subset=['time_obj'])
            if not valid_times.empty:
                st.markdown("---")
                st.subheader("⏳ Time")
                min_t, max_t = valid_times['time_obj'].min(), valid_times['time_obj'].max()
                if min_t != max_t:
                    try:
                        start_time, end_time = st.slider("Window", value=(min_t, max_t), format="MM-DD HH:mm")
                        df = df[(df['time_obj'] >= start_time) & (df['time_obj'] <= end_time)]
                    except: pass

        st.markdown("---")
        available_layers = current_db.get(selected_map, {}).keys()
        active_layers = [layer for layer in available_layers if st.checkbox(layer, value=True)]
        
        search_term = st.text_input("Search", placeholder="Player...")
        
    col1, col2 = st.columns([0.98, 0.02])
    with col1: 
        st.subheader(f"📍 {selected_map}")
    
    fig, map_size = render_map(df, selected_map, LOCKED_SETTINGS, search_term, active_layers, current_db)

    st.plotly_chart(
        fig, 
        use_container_width=True,
        config={
            'scrollZoom': True, 
            'displayModeBar': True, 
            'displaylogo': False,
            'modeBarButtonsToRemove': ['select2d', 'lasso2d', 'autoScale2d', 'resetScale2d']
        }
    )

if __name__ == "__main__":
    main()
