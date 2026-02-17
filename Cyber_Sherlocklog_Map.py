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
    # Map Image Alignment (Verified)
    "img_off_x": 127,
    "img_off_y": 628,
    "img_scale": 1.04,
    "img_opacity": 1.0,
    
    # Log Data Alignment (Verified from your manual tuning)
    "log_off_x": 150,
    "log_off_y": 40,
    
    # Logic Defaults
    "swap_xy": False,
    "show_grid": True,
    "show_towns": True
}

MAP_CONFIG = {
    "Chernarus": {"size": 15360, "image": "map_chernarus.png"}, 
    "Livonia": {"size": 12800, "image": "map_livonia.png"},
    "Sakhal": {"size": 8192, "image": "map_sakhal.png"}
}

# --- DATABASE ---
TOWN_DATA = {
    "Chernarus": [
        {"name": "NWAF", "x": 4600, "y": 10200},
        {"name": "Severograd", "x": 8400, "y": 12700},
        {"name": "Stary Sobor", "x": 6050, "y": 7750},
        {"name": "Novy Sobor", "x": 7100, "y": 7700},
        {"name": "Vybor", "x": 3750, "y": 8900},
        {"name": "Gorka", "x": 9500, "y": 8800},
        {"name": "Chernogorsk", "x": 6650, "y": 2600},
        {"name": "Elektrozavodsk", "x": 10450, "y": 2300},
        {"name": "Berezino", "x": 12400, "y": 9600},
        {"name": "Zelenogorsk", "x": 2750, "y": 5300},
        {"name": "Tisy Base", "x": 1700, "y": 14000},
        {"name": "Krasnostav", "x": 11200, "y": 12300},
        {"name": "Solnichniy", "x": 13350, "y": 6200},
        {"name": "Kamyshovo", "x": 12000, "y": 3500},
        {"name": "Balota", "x": 4400, "y": 2400},
        {"name": "VMC", "x": 4500, "y": 8300},
        {"name": "Altar", "x": 8100, "y": 9300},
        {"name": "Radio Zenit", "x": 7900, "y": 9700}
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
        "🛡️ Military": [{"name": "Tisy Radar", "x": 1700, "y": 14000}],
        "🏰 Castles": [{"name": "Devil's Castle", "x": 6800, "y": 11500}],
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
    # This function is kept simple as we rely on the renderer to handle offsets now
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
                    l_x.append(loc['x'])
                    l_y.append(loc['y'])
                    l_txt.append(loc['name'])
                
                color = "cyan"
                if "Military" in layer_name: color = "red"
                elif "Castle" in layer_name: color = "purple"
                
                fig.add_trace(go.Scatter(
                    x=l_x, y=l_y, mode='markers',
                    marker=dict(size=9, color=color, symbol='diamond', line=dict(width=1, color='black')),
                    text=l_txt, name=layer_name, 
                    hovertemplate="<b>%{text}</b><br>Game: %{x:.0f} / %{y:.0f}<extra></extra>"
                ))

    # D. PLAYERS (LOGS) - HARDCODED FORMAT <X, Y, Z>
    if not df.empty:
        # According to your server logs: 
        # raw_1 = X
        # raw_2 = Y (North) -> THIS IS THE ONE WE USE
        # raw_3 = Z (Height)
        
        raw_x = df["raw_1"]
        raw_y = df["raw_2"] 
        
        # Apply the Hardcoded "Winning" Log Offset
        # We process it as Vector Arrays for performance
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
                
                fig.add_trace(go.Scatter(
                    x=p_fx, y=p_fy, mode='text',
                    text=df_plot["icon"],
                    textfont=dict(size=14),
                    customdata=list(zip(df_plot["time_str"], df_plot["name"], p_x, p_y)),
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
        # Massive Top Margin (80px) ensures Modebar does not cover grid
        margin={"l": 40, "r": 40, "t": 80, "b": 40}, 
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        dragmode="pan", 
        hovermode="closest", showlegend=True,
        # Legend moved to Bottom Left to stop overlapping map
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
    # AGGRESSIVE CSS to kill Header, Menu, and Footer
    st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        [data-testid="stSidebar"] { background-color: #262730; }
        
        /* HIDE HEADER completely */
        header[data-testid="stHeader"] { display: none !important; }
        
        /* HIDE Main Menu (Hamburger) and Footer */
        #MainMenu { display: none !important; }
        footer { display: none !important; }
        
        /* HIDE Decoration bar */
        [data-testid="stDecoration"] { display: none !important; }
        
        /* Push content up to fill the void */
        .block-container { 
            padding-top: 1rem !important; 
            padding-bottom: 0rem !important; 
        }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🗺️ Intel Control")
        selected_map = st.selectbox("Map", list(MAP_CONFIG.keys()))
        
        st.write("---")
        uploaded_log = st.file_uploader("1. Upload Logs", type=['adm', 'rpt', 'log'])
        
        st.caption("ℹ️ **Upload POI DB**: Optional. CSV for permanent bases/traders.")
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
    
    # Render with HARDCODED LOCKED settings
    fig, map_size = render_map(df, selected_map, LOCKED_SETTINGS, search_term, active_layers, current_db)

    # PURE VIEWER MODE: All interactive features disabled
    # config dictionary explicitly removes selection tools
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
