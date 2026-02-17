import streamlit as st
import plotly.graph_objects as go
import re
import pandas as pd
from PIL import Image
from datetime import datetime

# --- 1. CONFIGURATION & SAVED CALIBRATION ---
st.set_page_config(layout="wide", page_title="DayZ Intel Mapper")

# ⚠️ FINAL CALIBRATION (Map Image Alignment)
DEFAULT_CALIBRATION = {
    "img_off_x": 127,   
    "img_off_y": 628,   
    "img_scale": 1.04,  
    "target_x": 7464,   
    "target_y": 7682,
    "log_off_x": 0,     # New: Default Log Offset X
    "log_off_y": 0      # New: Default Log Offset Y
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

MARKER_ICONS = {
    "Base": "🏠", "Vehicle": "🚗", "Body": "💀", 
    "Loot": "🎒", "POI": "📍", "Enemy": "⚔️"
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
    time_pattern = re.compile(r'^(\d{2}:\d{2}:\d{2})')

    for line in lines:
        coord_match = coord_pattern.search(line)
        if coord_match:
            v1, v2, v3 = coord_match.groups()
            name_match = name_pattern.search(line)
            time_match = time_pattern.search(line)
            name = name_match.group(1) if name_match else "Unknown"
            log_time = None
            if time_match:
                try:
                    log_time = datetime.strptime(time_match.group(1), "%H:%M:%S").time()
                except: pass
            
            logs.append({
                "time_obj": log_time, "name": name,
                "raw_1": float(v1), "raw_2": float(v2), "raw_3": float(v3),
                "activity": line.strip()[:150] 
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
    # Apply Log Offsets (Only affects logs, handled in render loop usually, but applied here for simplicity if passed)
    # Note: We apply log offsets in the RENDER loop to avoid messing up markers.
    
    final_x = game_y if settings['swap_xy'] else game_x
    final_y = game_x if settings['swap_xy'] else game_y
    return final_x, final_y

def reverse_transform(plot_x, plot_y, settings):
    game_x = plot_x
    game_y = plot_y
    if settings['swap_xy']: return game_y, game_x
    return game_x, game_y

# --- 4. RENDER ENGINE ---
def render_map(df, map_name, settings, search_term, custom_markers, active_layers, poi_db, cal_target):
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

    # B. PHYSICAL GRID TRACE
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

    # C. SENSOR LAYER
    fig.add_trace(go.Heatmap(
        z=[[0, 0], [0, 0]], x=[0, map_size], y=[0, map_size],
        opacity=0, showscale=False, hoverinfo="none", 
        hovertemplate="<extra></extra>"
    ))

    # D. CALIBRATION TARGET
    if cal_target['active']:
        tx, ty = transform_coords(cal_target['x'], cal_target['y'], settings)
        fig.add_trace(go.Scatter(
            x=[tx], y=[ty], mode='markers+text',
            marker=dict(size=25, color='red', symbol='cross-thin', line=dict(width=3, color='red')),
            text=["🎯 TARGET"], textposition="top center",
            textfont=dict(color="red", size=16, family="Arial Black"),
            hovertemplate="Target<br>Game: %{x:.0f} / %{y:.0f}<extra></extra>",
            name="Calibration Target"
        ))

    # E. TOWNS
    if settings['show_towns'] and map_name in TOWN_DATA:
        t_x, t_y, t_names = [], [], []
        for town in TOWN_DATA[map_name]:
            tx, ty = transform_coords(town['x'], town['y'], settings)
            t_x.append(tx); t_y.append(ty); t_names.append(town['name'])
        
        fig.add_trace(go.Scatter(
            x=t_x, y=t_y, mode='markers+text', text=t_names, textposition="top center",
            marker=dict(size=6, color='yellow', line=dict(width=1, color='black')),
            textfont=dict(family="Arial Black", size=14, color="black"), 
            hovertemplate="<b>%{text}</b><br>Game: %{x:.0f} / %{y:.0f}<extra></extra>",
            name="Towns"
        ))

    # F. POI LAYERS
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

    # G. CUSTOM MARKERS
    if custom_markers:
        c_x, c_y, c_text = [], [], []
        for m in custom_markers:
            cx, cy = transform_coords(m['x'], m['y'], settings)
            c_x.append(cx); c_y.append(cy)
            c_text.append(MARKER_ICONS.get(m['type'], "📍"))

        fig.add_trace(go.Scatter(
            x=c_x, y=c_y, mode='text', text=c_text, textfont=dict(size=24),
            name="Custom", hoverinfo="text", hovertext=[m['label'] for m in custom_markers]
        ))

    # H. PLAYERS (LOGS) + LOG OFFSETS
    if not df.empty:
        raw_x = df["raw_1"]
        if settings['log_format'] == "Format: <X, Y, Z>":
            raw_y = df["raw_2"] 
        else:
            raw_y = df["raw_3"] 
            
        fx, fy = transform_coords(raw_x, raw_y, settings)
        
        # APPLY LOG OFFSET (This shifts ONLY the logs)
        fx = fx + settings['log_off_x']
        fy = fy + settings['log_off_y']
        
        colors = ['red'] * len(df)
        sizes = [7] * len(df)
        if search_term:
            mask = df['name'].str.contains(search_term, case=False, na=False)
            colors = ['lime' if m else 'rgba(255,0,0,0.1)' for m in mask]
            sizes = [15 if m else 5 for m in mask]

        fig.add_trace(go.Scatter(
            x=fx, y=fy, mode='markers',
            marker=dict(size=sizes, color=colors, line=dict(width=1, color='white')),
            text=df["name"], customdata=df["activity"],
            hovertemplate="<b>%{text}</b><br>Game: %{x:.0f} / %{y:.0f}<br>%{customdata}<extra></extra>",
            name="Logs"
        ))

    # I. RULERS
    grid_vals_x = []
    grid_text_x = []
    for i in range(16): 
        grid_vals_x.append(i * 1000)
        grid_text_x.append(f"{i:02d}")

    grid_vals_y = []
    grid_text_y = []
    for i in range(16): 
        grid_vals_y.append(i * 1000)      
        grid_text_y.append(f"{15-i:02d}")

    # J. LAYOUT
    fig.update_layout(
        height=900,
        margin={"l": 40, "r": 40, "t": 40, "b": 40},
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        dragmode="pan" if settings['click_mode'] == "Navigate" else False,
        hovermode="closest", showlegend=True,
        legend=dict(yanchor="top", y=0.95, xanchor="right", x=0.99, bgcolor="rgba(0,0,0,0.6)", font=dict(color="white")),
        
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
    if 'custom_markers' not in st.session_state: st.session_state['custom_markers'] = []
    
    st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        [data-testid="stSidebar"] { background-color: #262730; }
        [data-testid="stSidebar"] * { color: #cccccc !important; }
        .block-container { padding-top: 1rem !important; }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🗺️ Intel Control")
        selected_map = st.selectbox("Map", list(MAP_CONFIG.keys()))
        
        st.write("---")
        uploaded_log = st.file_uploader("1. Upload Logs", type=['adm', 'rpt', 'log'])
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
                    start_time, end_time = st.slider("Window", value=(min_t, max_t), format="HH:mm:ss")
                    df = df[(df['time_obj'] >= start_time) & (df['time_obj'] <= end_time)]

        st.markdown("---")
        available_layers = current_db.get(selected_map, {}).keys()
        active_layers = [layer for layer in available_layers if st.checkbox(layer, value=True)]
        
        click_mode = st.radio("Mode", ["Navigate", "🎯 Add Marker"], horizontal=True)
        search_term = st.text_input("Search", placeholder="Player...")
        
        st.write("---")
        st.subheader("🔧 Calibration")

        with st.form("calibration_form"):
            with st.expander("🎯 Calibration Target", expanded=True):
                st.caption("Coordinates of known landmark.")
                show_target = st.checkbox("Show Target", value=True)
                target_x = st.number_input("Target X", value=DEFAULT_CALIBRATION['target_x'], step=10)
                target_y = st.number_input("Target Y", value=DEFAULT_CALIBRATION['target_y'], step=10)

            with st.expander("🖼️ Map Image", expanded=True):
                st.info("Align map to Target.")
                img_off_x = st.slider("Image X", -2000, 2000, DEFAULT_CALIBRATION['img_off_x'], 10, key="cal_img_x_final_12") 
                img_off_y = st.slider("Image Y", -2000, 2000, DEFAULT_CALIBRATION['img_off_y'], 10, key="cal_img_y_final_12") 
                img_scale = st.slider("Image Scale", 0.8, 1.2, DEFAULT_CALIBRATION['img_scale'], 0.001, key="cal_img_scale_final_12") 
                img_opacity = st.slider("Opacity", 0.1, 1.0, 1.0, 0.1)

            with st.expander("⚙️ Settings (Log Tuning)", expanded=True):
                log_format = st.radio(
                    "📂 Log Format",
                    ["Format: <X, Y, Z>", "Format: <X, Height, Y>"],
                    index=0,
                    help="Switch this if dots appear at the bottom edge."
                )
                # NEW: LOG OFFSETS
                st.write("📍 **Log Alignment (Fine Tune)**")
                log_off_x = st.slider("Log X Offset", -1000, 1000, DEFAULT_CALIBRATION['log_off_x'], 10, key="cal_log_x")
                log_off_y = st.slider("Log Y Offset", -1000, 1000, DEFAULT_CALIBRATION['log_off_y'], 10, key="cal_log_y")
                
                swap_xy = st.checkbox("Swap X/Y Inputs", False)
                show_grid = st.checkbox("Show Grid (0-15)", True)
                show_towns = st.checkbox("Show Towns", True)

            applied = st.form_submit_button("✅ Apply Calibration")
            
        settings = {
            "img_off_x": img_off_x, "img_off_y": img_off_y, "img_scale": img_scale, "img_opacity": img_opacity,
            "log_format": log_format, "swap_xy": swap_xy, 
            "log_off_x": log_off_x, "log_off_y": log_off_y, # Pass offsets to render
            "click_mode": click_mode, "show_grid": show_grid, "show_towns": show_towns
        }
        
        cal_target = {"active": show_target, "x": target_x, "y": target_y}
            
        if st.session_state['custom_markers'] and st.button("Clear Markers"):
            st.session_state['custom_markers'] = []
            st.rerun()

    col1, col2 = st.columns([0.85, 0.15])
    with col1: 
        st.subheader(f"📍 {selected_map}")
        st.caption("ℹ️ Click to Add Markers. Pop-up shows GPS.")
    
    fig, map_size = render_map(df, selected_map, settings, search_term, st.session_state['custom_markers'], active_layers, current_db, cal_target)

    event = st.plotly_chart(
        fig, on_select="rerun", selection_mode="points", use_container_width=True,
        config={'scrollZoom': True, 'displayModeBar': True, 'modeBarButtonsToAdd': ['zoomIn2d', 'zoomOut2d', 'resetScale2d', 'pan2d'], 'displaylogo': False}
    )

    if click_mode == "🎯 Add Marker" and len(event.selection.points) > 0:
        p = event.selection.points[0]
        if 'x' in p and 'y' in p:
            gx, gy = reverse_transform(p['x'], p['y'], settings)
            @st.dialog("Add Marker")
            def add_marker_dialog():
                gps_x = gx / 10000
                gps_y = (map_size - gy) / 10000
                
                st.write(f"GPS: X: {gps_x:.2f} Y: {gps_y:.2f}")
                st.write(f"Game: {gx:.0f} / {gy:.0f}")
                
                m_type = st.selectbox("Type", list(MARKER_ICONS.keys()))
                m_label = st.text_input("Label")
                if st.button("Save"):
                    st.session_state['custom_markers'].append({"type": m_type, "label": m_label, "x": gx, "y": gy})
                    st.rerun()
            add_marker_dialog()

if __name__ == "__main__":
    main()
