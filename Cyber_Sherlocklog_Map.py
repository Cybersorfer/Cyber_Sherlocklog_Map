import streamlit as st
import plotly.graph_objects as go
import re
import pandas as pd
from PIL import Image
import os

# --- 1. CONFIGURATION ---
MAP_CONFIG = {
    "Chernarus": {
        "size": 15360,
        "image": "map_chernarus.png"
    },
    "Livonia": {
        "size": 12800,
        "image": "map_livonia.png"
    },
    "Sakhal": {
        "size": 8192, # Approximate, adjust if needed
        "image": "map_sakhal.png"
    }
}

# --- 2. LOG PARSING ENGINE ---
def parse_log_file(uploaded_file):
    """
    Reads a DayZ log file and extracts coordinates using Regex.
    Looks for patterns like: <1234.5, 67.8, 9012.3>
    """
    logs = []
    
    # Decodes bytes to string
    content = uploaded_file.getvalue().decode("utf-8")
    lines = content.split('\n')

    # Regex to find vectors: <X, Y, Z> or similar
    # Matches: <digits.digits, digits.digits, digits.digits>
    coord_pattern = re.compile(r"<([0-9\.-]+),\s*([0-9\.-]+),\s*([0-9\.-]+)>")
    
    # Regex to try and find a player name near the coordinates
    # Looks for 'Player "Name"' or 'Identity "Name"'
    name_pattern = re.compile(r'(?:Player|Identity)\s+"([^"]+)"')

    for line in lines:
        coord_match = coord_pattern.search(line)
        if coord_match:
            # DayZ Log Vector is usually <East(X), Height(Y), North(Z)>
            x, y, z = coord_match.groups()
            
            # Extract name if present, else use line number
            name_match = name_pattern.search(line)
            name = name_match.group(1) if name_match else "Unknown/Object"

            # Basic clean up of the log line for display
            clean_details = line[:100] + "..." if len(line) > 100 else line

            logs.append({
                "name": name,
                "x": float(x),
                "z": float(z), # We use Z for the map's vertical axis
                "h": float(y), # Height
                "details": clean_details
            })
            
    return pd.DataFrame(logs)

# --- 3. MAP RENDERING ENGINE ---
def render_map(df, map_name):
    config = MAP_CONFIG[map_name]
    map_size = config["size"]
    img_path = config["image"]

    # Initialize Figure
    fig = go.Figure()

    # -- A. Load Map Image --
    # We attempt to load the image. If missing, we show a blank grid.
    try:
        img = Image.open(img_path)
        fig.add_layout_image(
            dict(
                source=img,
                xref="x",
                yref="y",
                x=0,
                y=map_size, # Plotly places image top-left corner here
                sizex=map_size,
                sizey=map_size,
                sizing="stretch",
                opacity=1,
                layer="below"
            )
        )
    except FileNotFoundError:
        st.warning(f"⚠️ Map image not found: `{img_path}`. Displaying grid only.")

    # -- B. Plot Data Points --
    if not df.empty:
        fig.add_trace(
            go.Scatter(
                x=df["x"],
                y=df["z"], # In Cartesian 2D plot, Y axis is the Game's North/South (Z)
                mode='markers',
                marker=dict(
                    size=8,
                    color='red',
                    symbol='circle',
                    line=dict(width=1, color='white')
                ),
                text=df["name"],
                customdata=df["details"],
                hovertemplate="<b>%{text}</b><br>Coords: %{x:.0f}, %{y:.0f}<br>Log: %{customdata}<extra></extra>"
            )
        )

    # -- C. Configure Axes & Layout --
    # Force the axis to match the game world size exactly
    fig.update_xaxes(range=[0, map_size], visible=False, showgrid=False)
    fig.update_yaxes(range=[0, map_size], visible=False, showgrid=False)

    fig.update_layout(
        width=800,
        height=800,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        plot_bgcolor="black",
        dragmode="pan", # Enables the "hand" tool by default like iZurvive
    )

    st.plotly_chart(fig, use_container_width=True)

# --- 4. MAIN APP INTERFACE ---
def main():
    st.set_page_config(layout="wide", page_title="Log Mapper Tool")
    
    st.title("🗺️ Interactive Server Log Mapper")
    st.markdown("Upload your **.ADM** or **.RPT** files to visualize coordinates.")

    # Sidebar Controls
    with st.sidebar:
        st.header("Settings")
        selected_map = st.selectbox("Select Terrain", options=list(MAP_CONFIG.keys()))
        
        uploaded_file = st.file_uploader("Upload Log File", type=['adm', 'rpt', 'txt', 'log'])
        
        st.info("**Tip:** Ensure your map images are in the same folder as this script.")

    # Main Processing
    if uploaded_file:
        with st.spinner("Parsing logs..."):
            df = parse_log_file(uploaded_file)
        
        if not df.empty:
            st.success(f"Found {len(df)} coordinates!")
            
            # Optional: Filter by Player Name
            all_players = ["All"] + list(df["name"].unique())
            selected_player = st.selectbox("Filter by Player/Entity", all_players)
            
            if selected_player != "All":
                df = df[df["name"] == selected_player]

            # Render the Map
            render_map(df, selected_map)
            
            # Show Raw Data Table
            with st.expander("View Raw Data"):
                st.dataframe(df)
        else:
            st.warning("No coordinates found in this file. Ensure the logs use format `<x, y, z>`.")
    else:
        # Show an empty map (placeholder) so the app looks nice on load
        render_map(pd.DataFrame(), selected_map)

if __name__ == "__main__":
    main()