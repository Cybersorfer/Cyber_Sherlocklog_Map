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

# --- 2. CACHED DATA LOADING (SPEED OPTIMIZATION) ---
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

# --- 3. MATH (STRICT DAYZ -> IMAGE CONVERSION) ---
def transform_coords(raw_x, raw_z, settings, map_size):
    # 1. SWAP X/Z (If log format differs)
    final_x = raw_z if settings['swap_xz'] else raw_x
    final_z = raw_x if settings['swap_xz'] else raw_z
    
    # 2. INVERT Z (DayZ N=15360 -> Image Top=0)
    # The image coordinate system starts at Top-Left (0,0).
    # DayZ coordinate system starts at Bottom-Left (0,0).
    # Therefore, Image Y = MapSize - DayZ Z.
    if settings['invert_z']: 
        final_z = map_size - final_z

    # 3. SCALE & OFFSET
    final_x = (final_x * settings['scale_factor']) + settings['off_x']
    final_z = (final_z * settings['scale_factor']) + settings['off_y']
    
    return final_x, final_z

def reverse_transform(plot_x, plot_y, settings, map_size):
    # Reverse Scale/Offset
    rx = (plot_x - settings['off_x']) / settings['scale_factor']
    rz = (plot_y - settings['off_y']) / settings['scale_factor']
    
    # Reverse Inversion
    if settings['invert_z']: 
        rz = map_size - rz
        
    game_x = rz if settings['swap_xz'] else rx
    game_z = rx if settings['swap_xz'] else rz
    return game_x, game_z

# --- 4. RENDER ENGINE (LOCKED ASPECT RATIO) ---
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
                x=0, y=0,           # Locked to Top-Left
                sizex=map_size, sizey=map_size,
                sizing="stretch",
                opacity=1,
                layer="below"
            )
        )
    else:
        fig.add_shape(type="rect", x0=0, y0=0, x1=map_size, y1=map_size, line=dict(color="RoyalBlue"))

    # B. GRID SYSTEM (Strict Overlay)
    if settings['show_grid']:
        tick_vals = []
        tick_text = []
        
        # 00 to 15 Loop
        for i in range(16):
            # Calculate exact pixel position for grid line
            raw_pos = i * 1000
            
            # X-Axis Ticks (Left to Right)
            t_x = (raw_pos * settings['scale_factor']) + settings['off_x']
            tick_vals.append(t_x)
            tick_text.append(f"{i:02d}")
            
            # Draw Grid Lines Manually to force them "Above" image
            # Vertical
            fig.add_shape(type="line", x0=t_x, y0=0, x1=t_x, y1=map_size,
                          line=dict(color="rgba(255, 255, 255, 0.2)", width=1), layer="above")
            
            # Horizontal (Y-Axis)
            # Since our Y-Axis is inverted (0 Top), the math is simple: 
            # 00 is at 0px, 01 is at 1000px, etc.
            t_y = (raw_pos * settings['scale_factor']) + settings['off_y']
            
            fig.add_shape(type="line", x0=0, y0=t_y, x1=map_size, y1=t_y,
                          line=dict(color="rgba(255, 255, 255, 0.2)", width=1), layer="above")

        # AXIS CONFIGURATION (LOCKED)
        fig.update_xaxes(
            visible=True, range=[0, map_size], side="top",
            tickmode="array", tickvals=tick_vals, ticktext=tick_text,
            tickfont=dict(size=14, color="white", family="Arial Black"),
            showgrid=False, zeroline=False,
            # CRITICAL: LOCK ASPECT RATIO
            constrain='domain'
        )
        
        fig.update_yaxes(
            visible=True, range=[map_size, 0], # 0 at TOP (Standard Image Coords)
            tickmode="array", tickvals=tick_vals, ticktext=tick_text,
            tickfont=dict(size=14, color="white", family="Arial Black"),
            showgrid=False, zeroline=False,
            # CRITICAL: LOCK ASPECT RATIO to X Axis so map doesn't float/squash
            scaleanchor="x", scaleratio=1,
            constrain='domain'
        )
    else:
        fig.update_xaxes(visible=False, range=[0, map_size], constrain='domain')
        fig.update_yaxes(visible=False, range=[map_size, 0], scaleanchor="x", scaleratio=1, constrain='domain')

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

    # G. LAYOUT (FIXED CONTAINER)
    fig.update_layout(
        height=800, # Fixed height to prevent website jumping
        margin={"l": 40, "r": 40, "t": 40, "b": 10},
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        dragmode="pan" if settings['click_mode'] == "Navigate" else False,
        showlegend=True,
        legend=dict(yanchor="top", y=0.95, xanchor="right", x=0.99, bgcolor="rgba(0,0,0,0.6)", font=dict(color="white"))
    )
    return fig, map_size

# --- 5. UI MAIN ---
def main():
    if 'custom_markers' not in st.session_state: st.session_state['custom_markers'] = []
    
    st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        [data-testid="stSidebar"] { background-color: #262730; }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, 
        [data-testid="stFileUploader"] small, .streamlit-expanderHeader p { color: #cccccc !important; }
        .block-container { padding-top: 1rem !important; }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🗺️ Intel Control")
        selected_map = st.selectbox("Map", list(MAP_CONFIG.keys()))
        
        st.write("---")
        uploaded_log = st.file_uploader("1. Upload Logs (.ADM/.RPT)", type=['adm', 'rpt', 'log'])
        uploaded_csv = st.file_uploader("2. Upload POI Database (.CSV)", type=['csv'])
        
        if uploaded_csv:
            current_db = parse_poi_csv(uploaded_csv)
            st.success("✅ Custom Database")
        else:
            current_db = DEFAULT_POI_DATABASE

        df = parse_log_file_content(uploaded_log.getvalue()) if uploaded_log else pd.DataFrame()

        if not df.empty and 'time_obj' in df.columns:
            valid_times = df.dropna(subset=['time_obj'])
            if not valid_times.empty:
                st.markdown("---")
                st.subheader("⏳ Time Filter")
                min_t, max_t = valid_times['time_obj'].min(), valid_times['time_obj'].max()
                if min_t != max_t:
                    start_time, end_time = st.slider("Window", value=(min_t, max_t), format="HH:mm:ss")
                    df = df[(df['time_obj'] >= start_time) & (df['time_obj'] <= end_time)]

        st.markdown("---")
        st.subheader("👁️ Layers")
        available_layers = current_db.get(selected_map, {}).keys()
        active_layers = [layer for layer in available_layers if st.checkbox(layer, value=True)]
        
        show_grid = st.checkbox("Show Grid (0-15)", value=True)
        show_towns = st.checkbox("Show Town Names", value=True)

        st.markdown("---")
        click_mode = st.radio("🖱️ Mouse Mode", ["Navigate", "🎯 Add Marker"], horizontal=True)
        search_term = st.text_input("🔍 Search", placeholder="Player Name...")
        
        with st.expander("⚙️ Calibration"):
            settings = {
                "use_y_as_z": st.checkbox("Fix Ocean Dots", True),
                "swap_xz": st.checkbox("Swap X/Z", False),
                "invert_z": st.checkbox("Invert Vertical", True), # TRUE Default for Image Alignment
                "off_x": st.slider("X Off", -2000, 2000, 0, 10),
                "off_y": st.slider("Y Off", -2000, 2000, 0, 10),
                "scale_factor": st.slider("Scale", 0.8, 1.2, 1.0, 0.005),
                "click_mode": click_mode, "show_grid": show_grid, "show_towns": show_towns
            }
            
        if st.session_state['custom_markers'] and st.button("Clear Markers"):
            st.session_state['custom_markers'] = []
            st.rerun()

    col1, col2 = st.columns([0.85, 0.15])
    with col1: st.subheader(f"📍 {selected_map}")
    
    fig, map_size = render_map(df, selected_map, settings, search_term, st.session_state['custom_markers'], active_layers, current_db)

    # EVENT HANDLING
    event = st.plotly_chart(
        fig, on_select="rerun", selection_mode="points", use_container_width=True,
        config={'scrollZoom': True, 'displayModeBar': True, 'modeBarButtonsToAdd': ['zoomIn2d', 'zoomOut2d', 'resetScale2d', 'pan2d'], 'displaylogo': False}
    )

    if click_mode == "🎯 Add Marker" and len(event.selection.points) > 0:
        p = event.selection.points[0]
        # Robust check for missing x/y in event data
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
