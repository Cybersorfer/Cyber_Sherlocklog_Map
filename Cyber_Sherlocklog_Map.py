import streamlit as st
import plotly.graph_objects as go
import re
import pandas as pd
from PIL import Image
from datetime import datetime, time

# --- 1. CONFIGURATION ---
st.set_page_config(layout="wide", page_title="DayZ Intel Mapper")

MAP_CONFIG = {
    "Chernarus": {"size": 15360, "image": "map_chernarus.png"},
    "Livonia": {"size": 12800, "image": "map_livonia.png"},
    "Sakhal": {"size": 8192, "image": "map_sakhal.png"}
}

TOWN_DATA = {
    "Chernarus": [
        {"name": "NWAF", "x": 4600, "z": 10200},
        {"name": "Stary Sobor", "x": 6050, "z": 7750},
        {"name": "Novy Sobor", "x": 7100, "z": 7700},
        {"name": "Vybor", "x": 3750, "z": 8900},
        {"name": "Gorka", "x": 9500, "z": 8850},
        {"name": "Chernogorsk", "x": 6650, "z": 2600},
        {"name": "Elektrozavodsk", "x": 10450, "z": 2300},
        {"name": "Berezino", "x": 12400, "z": 9700},
        {"name": "Zelenogorsk", "x": 2750, "z": 5300},
        {"name": "Severograd", "x": 8400, "z": 13700},
        {"name": "Tisy", "x": 1700, "z": 14000},
        {"name": "Krasnostav", "x": 11200, "z": 12300},
        {"name": "Solnichniy", "x": 13300, "z": 6200},
        {"name": "Kamyshovo", "x": 12000, "z": 3500},
        {"name": "Balota", "x": 4400, "z": 2400},
        {"name": "VMC", "x": 4500, "z": 8300},
        {"name": "Altar", "x": 8100, "z": 9300},
        {"name": "Radio Zenit", "x": 7900, "z": 9700}
    ],
    "Livonia": [
        {"name": "Topolin", "x": 6200, "z": 11000},
        {"name": "Brena", "x": 6300, "z": 11800},
        {"name": "Nadbor", "x": 5600, "z": 4500},
        {"name": "Sitnik", "x": 6300, "z": 2200},
        {"name": "Radunin", "x": 9500, "z": 6800}
    ],
    "Sakhal": []
}

DEFAULT_POI_DATABASE = {
    "Chernarus": {
        "🛡️ Military": [{"name": "Tisy Radar", "x": 1700, "z": 14000}],
        "🏰 Castles": [{"name": "Devil's Castle", "x": 6800, "z": 11500}],
    }
}

MARKER_ICONS = {
    "Base": "🏠", "Vehicle": "🚗", "Body": "💀", 
    "Loot": "🎒", "POI": "📍", "Enemy": "⚔️"
}

# --- 2. CACHED LOADERS ---
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
                "time_obj": log_time,
                "name": name,
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
            new_db[m_name][cat].append({
                "name": row['name'], "x": float(row['x']), "z": float(row['z'])
            })
        return new_db
    except Exception:
        return DEFAULT_POI_DATABASE

# --- 3. MATH ---
def transform_coords(raw_x, raw_z, settings, map_size):
    # Swap X/Z
    final_x = raw_z if settings['swap_xz'] else raw_x
    final_z = raw_x if settings['swap_xz'] else raw_z
    
    # Invert Z (DayZ N=Max -> Image Top=0)
    if settings['invert_z']: 
        final_z = map_size - final_z

    # Scale/Offset (Applied to COORDINATES)
    final_x = (final_x * settings['scale_factor']) + settings['off_x']
    final_z = (final_z * settings['scale_factor']) + settings['off_y']
    
    return final_x, final_z

def reverse_transform(plot_x, plot_y, settings, map_size):
    rx = (plot_x - settings['off_x']) / settings['scale_factor']
    rz = (plot_y - settings['off_y']) / settings['scale_factor']
    
    if settings['invert_z']: 
        rz = map_size - rz
        
    game_x = rz if settings['swap_xz'] else rx
    game_z = rx if settings['swap_xz'] else rz
    return game_x, game_z

# --- 4. RENDER ENGINE ---
def render_map(df, map_name, settings, search_term, custom_markers, active_layers, poi_db):
    config = MAP_CONFIG[map_name]
    map_size = config["size"]
    fig = go.Figure()

    # A. IMAGE LAYER (Background)
    img = load_map_image(config["image"])
    if img:
        fig.add_layout_image(
            dict(
                source=img,
                xref="x", yref="y",
                x=settings['img_off_x'], 
                y=settings['img_off_y'],
                sizex=map_size * settings['img_scale'], 
                sizey=map_size * settings['img_scale'],
                sizing="stretch",
                opacity=settings['img_opacity'],
                layer="below"
            )
        )
    else:
        fig.add_shape(type="rect", x0=0, y0=0, x1=map_size, y1=map_size, line=dict(color="RoyalBlue"))

    # B. COORDINATE SYSTEM & RULERS (Native Plotly Axes)
    # We define the tick marks to be exactly in the center of the 1000m grids
    # and the grid lines to be exactly on the 1000m marks.
    
    tick_vals = []
    tick_text = []
    
    # Generate labels 00 to 16
    for i in range(17):
        pos = (i * 1000)
        # Apply the coordinate calibration to the grid itself
        # Note: We are transforming the GRID to match the user's calibration settings
        t_pos = (pos * settings['scale_factor']) + (settings['off_x'] if i==0 else 0) # Base logic
        
        # Actually, simpler logic: The axis represents the transformed space.
        # We just label the standard intervals.
        tick_vals.append(i * 1000)
        tick_text.append(f"{i:02d}")

    # C. TOWNS
    if settings['show_towns'] and map_name in TOWN_DATA:
        t_x, t_y, t_names = [], [], []
        for town in TOWN_DATA[map_name]:
            tx, ty = transform_coords(town['x'], town['z'], settings, map_size)
            t_x.append(tx); t_y.append(ty); t_names.append(town['name'])
        
        fig.add_trace(go.Scatter(
            x=t_x, y=t_y, mode='markers+text', text=t_names, textposition="top center",
            marker=dict(size=6, color='yellow', line=dict(width=1, color='black')),
            textfont=dict(family="Arial Black", size=14, color="black"), 
            hoverinfo='none', name="Towns"
        ))

    # D. POI LAYERS
    if map_name in poi_db:
        for layer_name, locations in poi_db[map_name].items():
            if layer_name in active_layers:
                l_x, l_y, l_txt = [], [], []
                for loc in locations:
                    tx, ty = transform_coords(loc['x'], loc['z'], settings, map_size)
                    l_x.append(tx); l_y.append(ty); l_txt.append(loc['name'])
                
                color = "cyan"
                if "Military" in layer_name: color = "red"
                elif "Castle" in layer_name: color = "purple"
                
                fig.add_trace(go.Scatter(
                    x=l_x, y=l_y, mode='markers',
                    marker=dict(size=9, color=color, symbol='diamond', line=dict(width=1, color='black')),
                    text=l_txt, name=layer_name, hoverinfo='text'
                ))

    # E. CUSTOM MARKERS
    if custom_markers:
        c_x, c_y, c_text = [], [], []
        for m in custom_markers:
            cx, cy = transform_coords(m['x'], m['z'], settings, map_size)
            c_x.append(cx); c_y.append(cy)
            c_text.append(MARKER_ICONS.get(m['type'], "📍"))

        fig.add_trace(go.Scatter(
            x=c_x, y=c_y, mode='text', text=c_text, textfont=dict(size=24),
            name="Custom", hoverinfo="text", hovertext=[m['label'] for m in custom_markers]
        ))

    # F. PLAYERS
    if not df.empty:
        raw_x = df["raw_1"]
        raw_z = df["raw_2"] if settings['use_y_as_z'] else df["raw_3"]
        fx, fz = transform_coords(raw_x, raw_z, settings, map_size)
        
        colors = ['red'] * len(df)
        sizes = [7] * len(df)
        if search_term:
            mask = df['name'].str.contains(search_term, case=False, na=False)
            colors = ['lime' if m else 'rgba(255,0,0,0.1)' for m in mask]
            sizes = [15 if m else 5 for m in mask]

        fig.add_trace(go.Scatter(
            x=fx, y=fz, mode='markers',
            marker=dict(size=sizes, color=colors, line=dict(width=1, color='white')),
            text=df["name"], customdata=df["activity"],
            hovertemplate="<b>%{text}</b><br>%{customdata}<extra></extra>",
            name="Logs"
        ))

    # G. LAYOUT
    # Calculate Axis Ranges based on Calibration
    # We want the axis to move based on the offset/scale so the grid moves with the dots
    
    # Base grid is 0 to map_size
    # Transformed Grid is: (0 * scale + off) to (map_size * scale + off)
    
    min_x = (0 * settings['scale_factor']) + settings['off_x']
    max_x = (map_size * settings['scale_factor']) + settings['off_x']
    
    min_y = (0 * settings['scale_factor']) + settings['off_y']
    max_y = (map_size * settings['scale_factor']) + settings['off_y']

    # We use tickvals logic to place grid lines every 1000 scaled units
    grid_ticks_x = []
    grid_labels_x = []
    for i in range(17):
        val = (i * 1000 * settings['scale_factor']) + settings['off_x']
        grid_ticks_x.append(val)
        grid_labels_x.append(f"{i:02d}")
        
    grid_ticks_y = []
    grid_labels_y = []
    for i in range(17):
        val = (i * 1000 * settings['scale_factor']) + settings['off_y']
        grid_ticks_y.append(val)
        grid_labels_y.append(f"{i:02d}")

    fig.update_layout(
        height=850,
        margin={"l": 40, "r": 40, "t": 40, "b": 40}, # Add margin for rulers
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        dragmode="pan" if settings['click_mode'] == "Navigate" else False,
        showlegend=True,
        legend=dict(yanchor="top", y=0.95, xanchor="right", x=0.99, bgcolor="rgba(0,0,0,0.6)", font=dict(color="white")),
        
        # --- X AXIS (TOP RULER) ---
        xaxis=dict(
            visible=True,
            range=[min_x - 1000, max_x + 1000],
            side="top", # Put ruler on top
            showgrid=settings['show_grid'],
            gridcolor="rgba(255, 255, 255, 0.2)",
            gridwidth=1,
            tickmode="array",
            tickvals=grid_ticks_x,
            ticktext=grid_labels_x,
            tickfont=dict(color="white", size=14, family="Arial Black"),
            zeroline=False
        ),

        # --- Y AXIS (LEFT RULER) ---
        yaxis=dict(
            visible=True,
            range=[max_y + 1000, min_y - 1000], # Inverted for Image coords
            side="left",
            showgrid=settings['show_grid'],
            gridcolor="rgba(255, 255, 255, 0.2)",
            gridwidth=1,
            tickmode="array",
            tickvals=grid_ticks_y,
            ticktext=grid_labels_y,
            tickfont=dict(color="white", size=14, family="Arial Black"),
            scaleanchor="x", # <--- KEY FIX: LOCK ASPECT RATIO (Square Grid)
            scaleratio=1,
            zeroline=False
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
        st.info("💡 Adjust sliders then click 'Apply' to update.")

        # --- FORM START ---
        with st.form("calibration_form"):
            # 1. Map Image Calibration
            with st.expander("🖼️ Map Image (Background)", expanded=False):
                img_off_x = st.slider("Image X", -4000, 4000, 0, 10)
                img_off_y = st.slider("Image Y", -4000, 4000, 0, 10)
                img_scale = st.slider("Image Scale", 0.5, 1.5, 1.0, 0.005)
                img_opacity = st.slider("Opacity", 0.1, 1.0, 1.0, 0.1)

            # 2. Coordinate Calibration
            with st.expander("📍 Coordinates (Grid/Pins)", expanded=True):
                use_y_as_z = st.checkbox("Fix Ocean (Use Y as Z)", True)
                swap_xz = st.checkbox("Swap X/Z", False)
                invert_z = st.checkbox("Invert Vertical (Z)", True)
                show_grid = st.checkbox("Show Grid", True)
                show_towns = st.checkbox("Show Towns", True)
                
                off_x = st.slider("Grid X Offset", -4000, 4000, 0, 10)
                off_y = st.slider("Grid Y Offset", -4000, 4000, 0, 10)
                scale_factor = st.slider("Grid Scale", 0.5, 1.5, 1.0, 0.005)

            # SUBMIT BUTTON (This fixes the "Takes forever" issue)
            applied = st.form_submit_button("✅ Apply Calibration")
            
        # Compile settings (Using defaults if form not yet submitted)
        settings = {
            "img_off_x": img_off_x, "img_off_y": img_off_y, "img_scale": img_scale, "img_opacity": img_opacity,
            "use_y_as_z": use_y_as_z, "swap_xz": swap_xz, "invert_z": invert_z,
            "off_x": off_x, "off_y": off_y, "scale_factor": scale_factor,
            "click_mode": click_mode, "show_grid": show_grid, "show_towns": show_towns
        }
            
        if st.session_state['custom_markers'] and st.button("Clear Markers"):
            st.session_state['custom_markers'] = []
            st.rerun()

    col1, col2 = st.columns([0.85, 0.15])
    with col1: st.subheader(f"📍 {selected_map}")
    
    fig, map_size = render_map(df, selected_map, settings, search_term, st.session_state['custom_markers'], active_layers, current_db)

    event = st.plotly_chart(
        fig, on_select="rerun", selection_mode="points", use_container_width=True,
        config={'scrollZoom': True, 'displayModeBar': True, 'modeBarButtonsToAdd': ['zoomIn2d', 'zoomOut2d', 'resetScale2d', 'pan2d'], 'displaylogo': False}
    )

    if click_mode == "🎯 Add Marker" and len(event.selection.points) > 0:
        p = event.selection.points[0]
        if 'x' in p and 'y' in p:
            gx, gz = reverse_transform(p['x'], p['y'], settings, map_size)
            @st.dialog("Add Marker")
            def add_marker_dialog():
                st.write(f"Grid: {gx/1000:.1f} / {gz/1000:.1f}")
                m_type = st.selectbox("Type", list(MARKER_ICONS.keys()))
                m_label = st.text_input("Label")
                if st.button("Save"):
                    st.session_state['custom_markers'].append({"type": m_type, "label": m_label, "x": gx, "z": gz})
                    st.rerun()
            add_marker_dialog()

if __name__ == "__main__":
    main()
