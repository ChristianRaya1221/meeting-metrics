# ----- IMPORTS ----- #
import copy
import streamlit as st
import plotly.express as px
import plotly.io as pio
import pandas as pd

from backend import (
    get_services,
    list_folders,
    find_general_meetings_folder,
    find_sheets_recursive,
    meeting_sort_key,
    load_selected_data_frames,
    sort_year,
    term_sort_key,
    YEAR_ORDER,
)

# ----- CONSTANTS / CONFIG ----- #
PLOTLY_TEMPLATE = "plotly_dark"
ROOT_FOLDER_ID = "0B5x6_lwAEhFZdkJnY3c1X1NxTVE"


# ----- STYLE ----- #
def inject_css() -> None:
    st.markdown(
        """
        <style>
        /* Center main content width */
        .block-container {
            max-width: 1200px;
            margin: 0 auto;
            padding-top: 2rem;
        }

        /* Center headings and paragraphs */
        h1, h2, h3, p { text-align: center; }

        /* Center widgets */
        div[data-testid="stSelectbox"],
        div[data-testid="stDownloadButton"] {
            display: flex;
            justify-content: center;
        }

        /* Make selectboxes consistent width */
        div[data-testid="stSelectbox"] > div {
            width: 525px;
            padding: 5px 10px;
        }

        /* Center all buttons + set width */
        div[data-testid="stButton"] {
            display: flex !important;
            justify-content: center !important;
        }
        div[data-testid="stButton"] button {
            width: 260px !important;
        }

        /* Center download buttons too */
        div[data-testid="stDownloadButton"] {
            display: flex !important;
            justify-content: center !important;
        }
        div[data-testid="stDownloadButton"] button {
            width: 260px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ----- SESSION STATE ----- #
def init_state() -> None:
    defaults = {
        "busy": False,
        "generated": False,
        "needs_load": False,
        "scope_choice": "quarter",  # "quarter" or "meeting"
        "data_frame_all": pd.DataFrame(),
        "signature": None,
        "_just_finished_loading": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ----- HELPERS ----- #
def set_scope(value: str) -> None:
    st.session_state.scope_choice = value
    st.session_state.generated = False  # require regenerate on scope change


def start_generate(signature) -> None:
    # prevent double-click
    if st.session_state.get("busy", False):
        return

    # If already up to date, do nothing
    if st.session_state.get("signature") == signature and st.session_state.get("generated", False):
        return

    st.session_state.signature = signature
    st.session_state.busy = True
    st.session_state.needs_load = True
    st.session_state.generated = False


def plotly_figure_to_png_bytes(fig) -> bytes:
    return pio.to_image(fig, format="png", scale=2)


def build_interactive_chart(
    data_frame: pd.DataFrame,
    column_name: str,
    chart_type: str,
    title_text: str,
    selected_palette,
    selected_text_color: str,
):
    def apply_interactive_style(fig, title_text_: str):
        fig.update_layout(
            template=PLOTLY_TEMPLATE,
            title=title_text_,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            legend=dict(font=dict(color="white")),
            showlegend=True,
        )
        return fig

    def apply_export_style(fig, title_text_: str):
        fig.update_layout(
            template=PLOTLY_TEMPLATE,
            title=title_text_,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=selected_text_color),
            legend=dict(font=dict(color=selected_text_color)),
            showlegend=True,
        )
        return fig

    counts = data_frame[column_name].value_counts().reset_index()
    counts.columns = [column_name, "Count"]

    total_n = int(counts["Count"].sum())
    title_with_total = f"{title_text} (Total: {total_n})"

    if column_name == "Year":
        counts["__sort_key"] = counts[column_name].apply(lambda v: YEAR_ORDER.get(v, 50))
        counts = counts.sort_values("__sort_key").drop(columns=["__sort_key"])
    else:
        counts = counts.sort_values("Count", ascending=False)

    if chart_type == "Bar graph":
        fig = px.bar(
            counts,
            x=column_name,
            y="Count",
            title=title_with_total,
            color_discrete_sequence=selected_palette,
            text="Count",
        )
        fig.update_layout(xaxis_tickangle=-45, height=480)
        fig.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x} = %{y}<extra></extra>",
        )

        fig = apply_interactive_style(fig, title_with_total)
        export_fig = apply_export_style(copy.deepcopy(fig), title_with_total)
        fig._export_variant = export_fig
        return fig

    if chart_type == "Horizontal bar graph":
        fig = px.bar(
            counts,
            x="Count",
            y=column_name,
            orientation="h",
            title=title_with_total,
            color_discrete_sequence=selected_palette,
            text="Count",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=480)
        fig.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y} = %{x}<extra></extra>",
        )

        fig = apply_interactive_style(fig, title_with_total)
        export_fig = apply_export_style(copy.deepcopy(fig), title_with_total)
        fig._export_variant = export_fig
        return fig

    if chart_type == "Pie chart":
        pie_df = counts.copy()
        pie_df[column_name] = pie_df[column_name].astype(str) + " = " + pie_df["Count"].astype(int).astype(str)

        fig = px.pie(
            pie_df,
            names=column_name,
            values="Count",
            title=title_with_total,
            color_discrete_sequence=selected_palette,
        )
        fig.update_traces(textinfo="percent", hovertemplate="%{label}<extra></extra>")
        fig.update_layout(showlegend=True, legend=dict(x=1.02, y=1, xanchor="left", yanchor="top"))

        fig = apply_interactive_style(fig, title_with_total)
        export_fig = apply_export_style(copy.deepcopy(fig), title_with_total)
        fig._export_variant = export_fig
        return fig

    return None


# ----- CACHED SERVICES / DATA ----- #
@st.cache_resource
def get_cached_services():
    return get_services()


@st.cache_data(show_spinner="Scanning spreadsheets...")
def cached_find_sheets(folder_id: str):
    # IMPORTANT: depends on drive service, but drive itself is cached resource
    drive, _ = get_cached_services()
    return find_sheets_recursive(drive, folder_id)


# ----- APP START ----- #
st.set_page_config(page_title="SHPE Analytics", page_icon="📊", layout="wide")
inject_css()
init_state()

st.title("SHPE Meeting Metrics Dashboard")
st.caption("Select a year → select a quarter → choose meeting/s → generate charts.")

drive, sheets = get_cached_services()

# ----- STEP 1: YEAR -----
st.subheader("Step 1: Select a YEAR folder")
years = sorted(list_folders(drive, ROOT_FOLDER_ID), key=lambda f: sort_year(f["name"]))
year_names = [f["name"] for f in years]

selected_year_name = st.selectbox(
    "Year folder",
    options=["Select a year..."] + year_names,
    disabled=st.session_state.busy,
    key="year_select",
)
if selected_year_name == "Select a year...":
    st.stop()
selected_year = next(f for f in years if f["name"] == selected_year_name)

# ----- STEP 2: QUARTER -----
st.subheader("Step 2: Select a QUARTER folder")
categories = list_folders(drive, selected_year["id"])
general_meetings_folder = find_general_meetings_folder(categories)

if not general_meetings_folder:
    st.warning("Couldn't auto-detect the General Meeting folder. Please pick it manually:")
    category_names = [f["name"] for f in categories]
    chosen_name = st.selectbox(
        "Select the General Meeting folder",
        options=["Select a folder..."] + category_names,
        key="manual_general_meeting_folder",
        disabled=st.session_state.busy,
    )
    if chosen_name == "Select a folder...":
        st.stop()
    general_meetings_folder = next(f for f in categories if f["name"] == chosen_name)

quarter_folders = sorted(list_folders(drive, general_meetings_folder["id"]), key=lambda f: term_sort_key(f["name"]))
quarter_names = [f["name"] for f in quarter_folders]

selected_quarter_name = st.selectbox(
    "Quarter folder",
    options=["Select a quarter..."] + quarter_names,
    disabled=st.session_state.busy,
    key="quarter_select",
)
if selected_quarter_name == "Select a quarter...":
    st.stop()
selected_quarter = next(f for f in quarter_folders if f["name"] == selected_quarter_name)

title_prefix = f"{selected_quarter['name']} {selected_year['name'].replace('SHPE ', '').strip()}"

# ----- STEP 3: MEETING SCOPE ----- #
st.subheader("Step 3: Select a meeting or the whole quarter")

sheet_files = cached_find_sheets(selected_quarter["id"])
if not sheet_files:
    st.warning("No spreadsheets found under this quarter.")
    st.stop()

sheet_files = sorted(sheet_files, key=lambda f: meeting_sort_key(f["name"]))
sheet_names = [f["name"] for f in sheet_files]

center_col = st.columns([1, 2, 2, 1])
with center_col[1]:
    st.button(
        ("✅ " if st.session_state.scope_choice == "quarter" else "") + "Entire Quarter (All General Meetings)",
        key="scope_quarter",
        on_click=set_scope,
        args=("quarter",),
        disabled=st.session_state.busy,
        use_container_width=True,
    )
with center_col[2]:
    st.button(
        ("✅ " if st.session_state.scope_choice == "meeting" else "") + "A Specific General Meeting",
        key="scope_meeting",
        on_click=set_scope,
        args=("meeting",),
        disabled=st.session_state.busy,
        use_container_width=True,
    )

selected_files = []
if st.session_state.scope_choice == "meeting":
    selected_meeting_name = st.selectbox(
        "Select a meeting spreadsheet",
        options=["Select a meeting..."] + sheet_names,
        disabled=st.session_state.busy,
        key="meeting_select",
    )
    if selected_meeting_name == "Select a meeting...":
        st.stop()
    selected_files = [f for f in sheet_files if f["name"] == selected_meeting_name]
else:
    selected_files = sheet_files

st.markdown(f"<p><b>Selected spreadsheets:</b> {len(selected_files)}</p>", unsafe_allow_html=True)
if not selected_files:
    st.stop()

st.markdown("---")

# ----- STEP 4: GENERATE ----- #
st.subheader("Step 4: Choose chart types and generate charts")

chart_type_options = ["Do not show", "Bar graph", "Horizontal bar graph", "Pie chart"]

selected_year_chart = st.selectbox(
    "Year chart type",
    options=chart_type_options,
    index=chart_type_options.index("Bar graph"),
    disabled=st.session_state.busy,
    key="year_chart_type",
)
selected_gender_chart = st.selectbox(
    "Gender chart type",
    options=chart_type_options,
    index=chart_type_options.index("Pie chart"),
    disabled=st.session_state.busy,
    key="gender_chart_type",
)
selected_major_chart = st.selectbox(
    "Major chart type",
    options=chart_type_options,
    index=chart_type_options.index("Horizontal bar graph"),
    disabled=st.session_state.busy,
    key="major_chart_type",
)

signature = (
    selected_year_name,
    selected_quarter_name,
    st.session_state.scope_choice,
    tuple(sorted([f["id"] for f in selected_files])),
    st.session_state.get("year_chart_type"),
    st.session_state.get("gender_chart_type"),
    st.session_state.get("major_chart_type"),
)

is_up_to_date = st.session_state.get("signature") == signature and st.session_state.get("generated", False)

# If selection changes, clear generated results
if st.session_state.get("signature") != signature:
    st.session_state.signature = signature
    st.session_state.generated = False
    st.session_state.needs_load = False
    st.session_state.data_frame_all = pd.DataFrame()

generate_charts_col = st.columns([1, 1, 1, 1, 1])
with generate_charts_col[2]:
    st.button(
        "Generate charts",
        type="primary",
        key="generate_btn",
        disabled=st.session_state.busy or is_up_to_date,
        on_click=start_generate,
        args=(signature,),
    )

if st.session_state.generated:
    st.caption("Charts are up to date. Change selections to regenerate.")

# Stop before charts if not generated
if (not st.session_state.generated) and (not st.session_state.needs_load):
    st.stop()

# Load only when needed
if st.session_state.needs_load:
    try:
        with st.spinner("Loading and standardizing rows from spreadsheets..."):
            st.session_state.data_frame_all = load_selected_data_frames(sheets, selected_files)

        st.session_state.generated = True
        st.session_state._just_finished_loading = True

    except Exception as e:
        st.session_state.generated = False
        st.error(f"Failed while loading sheets: {e}")
        st.session_state.busy = False
        st.session_state.needs_load = False
        st.stop()

    finally:
        st.session_state.busy = False
        st.session_state.needs_load = False

# Force ONE rerun after load so widgets unlock
if st.session_state.get("_just_finished_loading", False):
    st.session_state._just_finished_loading = False
    st.rerun()

data_frame_all = st.session_state.data_frame_all
if data_frame_all.empty:
    st.error("No rows loaded after standardization.")
    st.stop()

st.markdown("---")

# ----- CHART APPEARANCE ----- #
st.subheader("Chart appearance")

palette_options = {
    "Professional (Blue/Red)": px.colors.qualitative.Dark24,
    "Professional 2 (Light Blue/Light Pink)": px.colors.qualitative.Safe,
    "Vibrant (Dark Purple/Orange)": px.colors.qualitative.Plotly,
    "Vivid (Purple/Blue)": px.colors.qualitative.Prism,
    "Pastel (Light Pink/Light Blue)": px.colors.qualitative.Pastel1,
    "Cyber-Neon (Dark Purple/Dark Green)": px.colors.qualitative.Bold,
    "Vibrant Minimalist (Dark Blue/Dark Red)": px.colors.qualitative.G10,
}

c1, c2 = st.columns([2, 1], gap="large")
with c1:
    palette_name = st.selectbox("Color palette", options=list(palette_options.keys()), index=0, key="palette_name")
with c2:
    text_color_choice = st.radio(
        "Text color\n\n(Note: Only applies when chart is downloaded as PNG, not in interactive view)",
        options=["White", "Black"],
        horizontal=True,
        key="text_color_choice",
    )

selected_palette = palette_options[palette_name]
selected_text_color = "white" if text_color_choice == "White" else "black"

st.markdown("---")
st.subheader("Charts")

col1, col2, col3 = st.columns(3)

with col1:
    if selected_year_chart != "Do not show":
        if ("Year" not in data_frame_all.columns
            or (data_frame_all["Year"].nunique() == 1 and data_frame_all["Year"].iloc[0] == "(blank)")):
            st.info("This sheet has no Year column, so Year charts are unavailable.")
        else:
            year_title = f"{title_prefix} Year Distribution"
            fig = build_interactive_chart(data_frame_all, "Year", selected_year_chart, year_title, selected_palette, selected_text_color)
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
                export_fig = getattr(fig, "_export_variant", fig)
                st.download_button(
                    label="Download Year chart as PNG",
                    data=plotly_figure_to_png_bytes(export_fig),
                    file_name=f"{title_prefix} - Year Distribution.png",
                    mime="image/png",
                )

with col2:
    if selected_gender_chart != "Do not show":
        if ("Gender" not in data_frame_all.columns
            or (data_frame_all["Gender"].nunique() == 1 and data_frame_all["Gender"].iloc[0] == "(blank)")):
            st.info("This sheet has no Gender column, so Gender charts are unavailable.")
        else:
            gender_title = f"{title_prefix} Gender Distribution"
            fig = build_interactive_chart(data_frame_all, "Gender", selected_gender_chart, gender_title, selected_palette, selected_text_color)
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
                export_fig = getattr(fig, "_export_variant", fig)
                st.download_button(
                    label="Download Gender chart as PNG",
                    data=plotly_figure_to_png_bytes(export_fig),
                    file_name=f"{title_prefix} - Gender Distribution.png",
                    mime="image/png",
                )

with col3:
    if selected_major_chart != "Do not show":
        if ("Major" not in data_frame_all.columns
            or (data_frame_all["Major"].nunique() == 1 and data_frame_all["Major"].iloc[0] == "(blank)")):
            st.info("This sheet has no Major column, so Major charts are unavailable.")
        else:
            major_title = f"{title_prefix} Major Distribution"
            fig = build_interactive_chart(data_frame_all, "Major", selected_major_chart, major_title, selected_palette, selected_text_color)
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
                export_fig = getattr(fig, "_export_variant", fig)
                st.download_button(
                    label="Download Major chart as PNG",
                    data=plotly_figure_to_png_bytes(export_fig),
                    file_name=f"{title_prefix} - Major Distribution.png",
                    mime="image/png",
                )