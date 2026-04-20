import json
import pandas as pd
import geopandas as gpd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Italy Demographic Map", layout="wide")

# -----------------------------
# SETTINGS
# -----------------------------
DATA_PATH = "IT_Test.csv"
MAP_FEATURE_NAME_PATH = "properties.reg_name"

# -----------------------------
# HELPERS
# -----------------------------
def load_data(path):
    df = pd.read_csv(path)

    # Drop accidental index column if present
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])

    expected_cols = [
        "category",
        "indicator_name",
        "location_name",
        "gender",
        "age_min",
        "age_max",
        "estimate_dau",
        "estimate_mau_lower_bound",
        "estimate_mau_upper_bound",
        "month",
        "month_name",
        "year",
    ]

    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    numeric_cols = [
        "age_min",
        "age_max",
        "estimate_dau",
        "estimate_mau_lower_bound",
        "estimate_mau_upper_bound",
        "month",
        "year",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["location_name"] = df["location_name"].astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip()
    df["indicator_name"] = df["indicator_name"].astype(str).str.strip()
    df["gender"] = df["gender"].astype(str).str.strip()
    df["month_name"] = df["month_name"].astype(str).str.strip()

    df["age_range"] = (
        df["age_min"].fillna(0).astype("Int64").astype(str)
        + "-"
        + df["age_max"].fillna(0).astype("Int64").astype(str)
    )

    return df


@st.cache_data
def load_italy_geojson():
    regions = gpd.read_file(
        "https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_IT_regions.geojson"
    )

    # Fix names so they match your dataframe naming style
    regions["reg_name"] = regions["reg_name"].astype(str).str.strip()
    regions["reg_name"] = regions["reg_name"].str.replace(
        "Valle d'Aosta/Vallée d'Aoste", "Valle d'Aosta", regex=False
    )
    regions["reg_name"] = regions["reg_name"].str.replace(
        "Piemonte", "Piedmont", regex=False
    )
    regions["reg_name"] = regions["reg_name"].str.replace(
        "Lombardia", "Lombardy", regex=False
    )
    regions["reg_name"] = regions["reg_name"].str.replace(
        "Toscana", "Tuscany", regex=False
    )
    regions["reg_name"] = regions["reg_name"].str.replace(
        "Sardegna", "Sardinia", regex=False
    )

    return json.loads(regions.to_json())


def format_int(x):
    if pd.isna(x):
        return "-"
    return f"{int(round(x)):,}"


def build_map(filtered_df, geojson, metric):
    region_df = (
        filtered_df.groupby("location_name", as_index=False)[
            ["estimate_dau", "estimate_mau_lower_bound", "estimate_mau_upper_bound"]
        ]
        .sum()
    )

    fig = px.choropleth(
        region_df,
        geojson=geojson,
        locations="location_name",
        featureidkey=MAP_FEATURE_NAME_PATH,
        color=metric,
        hover_name="location_name",
        hover_data={
            "estimate_dau": ":,.0f",
            "estimate_mau_lower_bound": ":,.0f",
            "estimate_mau_upper_bound": ":,.0f",
        },
        color_continuous_scale="Reds",
    )

    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        title="Estimated Audience by Region",
        margin=dict(l=0, r=0, t=60, b=0),
        height=700,
    )
    return fig, region_df


# -----------------------------
# APP
# -----------------------------
st.title("Italy Regional Demographic Estimates")
st.caption("Streamlit app with year and month filters.")

try:
    df = load_data(DATA_PATH)
    geojson = load_italy_geojson()
except Exception as e:
    st.error("Error while loading data or map.")
    st.exception(e)
    st.stop()

# -----------------------------
# SIDEBAR FILTERS
# -----------------------------
st.sidebar.header("Filters")

# Year selector
year_options = sorted(df["year"].dropna().astype(int).unique().tolist())
selected_year = st.sidebar.selectbox("Year", year_options, index=len(year_options) - 1)

# Month selector based on selected year
year_df = df[df["year"] == selected_year].copy()

month_df = (
    year_df[["month", "month_name"]]
    .drop_duplicates()
    .sort_values("month")
)

month_options = month_df["month"].tolist()
month_name_map = dict(zip(month_df["month"], month_df["month_name"]))

selected_month = st.sidebar.selectbox(
    "Month",
    month_options,
    format_func=lambda m: f"{int(m)} - {month_name_map.get(m, str(m))}"
)

# Filter by year and month first
time_df = df[
    (df["year"] == selected_year) &
    (df["month"] == selected_month)
].copy()

# Category selector
category_options = sorted(time_df["category"].dropna().astype(str).unique().tolist())
selected_category = st.sidebar.selectbox("Category", category_options)

category_df = time_df[time_df["category"] == selected_category].copy()

# Indicator selector
indicator_options = sorted(category_df["indicator_name"].dropna().astype(str).unique().tolist())
selected_indicator = st.sidebar.selectbox("Indicator", indicator_options)

indicator_df = category_df[category_df["indicator_name"] == selected_indicator].copy()

# Gender selector
gender_options = sorted(indicator_df["gender"].dropna().astype(str).unique().tolist())
selected_gender = st.sidebar.selectbox("Gender", gender_options)

# Age slider
age_min_val = int(time_df["age_min"].min())
age_max_val = int(time_df["age_max"].max())

selected_age = st.sidebar.slider(
    "Age range",
    min_value=age_min_val,
    max_value=age_max_val,
    value=(age_min_val, age_max_val),
)

# Metric selector
metric_label_map = {
    "estimate_dau": "Estimate DAU",
    "estimate_mau_lower_bound": "Lower bound",
    "estimate_mau_upper_bound": "Upper bound",
}

selected_metric = st.sidebar.radio(
    "Map metric",
    options=list(metric_label_map.keys()),
    format_func=lambda x: metric_label_map[x],
)

# -----------------------------
# FINAL FILTER
# -----------------------------
filtered_df = time_df[
    (time_df["category"] == selected_category)
    & (time_df["indicator_name"] == selected_indicator)
    & (time_df["gender"] == selected_gender)
    & (time_df["age_min"] >= selected_age[0])
    & (time_df["age_max"] <= selected_age[1])
].copy()

# -----------------------------
# MAIN PAGE
# -----------------------------
selected_month_name = month_name_map.get(selected_month, str(selected_month))
st.subheader(
    f"{selected_category} → {selected_indicator} | {selected_month_name} {selected_year}"
)

if filtered_df.empty:
    st.warning("No rows match the selected filters.")
    st.stop()

fig, region_df = build_map(filtered_df, geojson, selected_metric)
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Regional values")

region_options = ["All regions"] + sorted(region_df["location_name"].tolist())
selected_region = st.selectbox("Choose a region", region_options)

if selected_region == "All regions":
    total_dau = filtered_df["estimate_dau"].sum()
    total_lower = filtered_df["estimate_mau_lower_bound"].sum()
    total_upper = filtered_df["estimate_mau_upper_bound"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Estimate DAU", format_int(total_dau))
    c2.metric("Lower bound", format_int(total_lower))
    c3.metric("Upper bound", format_int(total_upper))

    st.dataframe(
        region_df.sort_values(selected_metric, ascending=False).reset_index(drop=True),
        use_container_width=True,
    )
else:
    region_row = region_df[region_df["location_name"] == selected_region].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Estimate DAU", format_int(region_row["estimate_dau"]))
    c2.metric("Lower bound", format_int(region_row["estimate_mau_lower_bound"]))
    c3.metric("Upper bound", format_int(region_row["estimate_mau_upper_bound"]))

    st.dataframe(
        filtered_df[filtered_df["location_name"] == selected_region]
        .sort_values("estimate_dau", ascending=False)
        .reset_index(drop=True),
        use_container_width=True,
    )

with st.expander("Notes"):
    st.write("This version supports multiple months and years.")
    st.write("Next, we can add multiple countries and country-level drill-down.")
