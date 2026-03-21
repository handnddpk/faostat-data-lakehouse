import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pyiceberg.catalog import load_catalog

st.set_page_config(page_title="FAOSTAT Food Security Dashboard", layout="wide")

@st.cache_resource
def get_catalog():
    return load_catalog(
        "lakehouse", 
        **{
            "type": "sql",
            "uri": "postgresql+psycopg2://admin:password@postgres:5432/metastore",
            "warehouse": "s3a://lakehouse/warehouse",
            "s3.endpoint": "http://minio:9000",
            "s3.access-key-id": "minioadmin",
            "s3.secret-access-key": "minioadmin",
            "s3.path-style-access": "true"
        }
    )
    
@st.cache_data
def load_table(table_name):
    try:
        catalog = get_catalog()
        table = catalog.load_table(table_name)
        return table.scan().to_pandas()
    except Exception as e:
        st.error(f"Error loading table {table_name}: {e}")
        return pd.DataFrame()

st.title("🌾 Global Food Security Dashboard")

tab1, tab2, tab3, tab4 = st.tabs(["Production", "Trade", "Food Security", "Insights"])

with tab1:
    st.header("Global Crop Production")
    yearly_production_data = load_table("gold.yearly_crop_production")
    top_crops = load_table("gold.top_crops")
    
    if not top_crops.empty:
        fig = px.bar(
            top_crops.head(10), 
            x="crop", 
            y="global_production", 
            title="Top 10 Crops by Global Production",
            labels={"crop": "Crop", "global_production": "Global Production (tonnes)"},
            color="crop"
        )
        st.plotly_chart(fig, use_container_width=True)
        
    if not yearly_production_data.empty:
        selected_crop = st.multiselect(
            "Select Crops to View Production Trends", 
            options=yearly_production_data["crop"].unique(), 
            default=yearly_production_data["crop"].unique()[:5]
        )
        
        if selected_crop:
            filtered_data = yearly_production_data[yearly_production_data["crop"].isin(selected_crop)]
            fig = px.line(
                filtered_data, 
                x="year", 
                y="global_production", 
                color="crop", 
                title="Global Production Trends Over Time",
                labels={"year": "Year", "global_production": "Global Production (tonnes)", "crop": "Crop"}
            )
            st.plotly_chart(fig, use_container_width=True)
        

with tab2:
    st.header("International Trade")
    trade_balance_data = load_table("gold.trade_balance")
    
    if not trade_balance_data.empty:
        latest_year = trade_balance_data["year"].max()
        latest_data = trade_balance_data[trade_balance_data["year"] == latest_year]
        
        top_exporters = latest_data.nlargest(10, "exports")
        top_importers = latest_data.nlargest(10, "imports")
        
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                top_exporters, 
                x="country", 
                y="exports", 
                title=f"Top 10 Exporters in {latest_year}",
                labels={"country": "Country", "exports": "Export Quantity (tonnes)"},
                color="country"
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            fig = px.bar(
                top_importers, 
                x="country", 
                y="imports", 
                title=f"Top 10 Importers in {latest_year}",
                labels={"country": "Country", "imports": "Import Quantity (tonnes)"},
                color="country"
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.header("Global Food Security Indicators")
    food_security_data = load_table("gold.food_security")

    if not food_security_data.empty:
        latest_year = food_security_data["year"].max()
        latest_data = food_security_data[food_security_data["year"] == latest_year]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_ratio = latest_data["self_sufficiency_ratio"].mean()
            st.metric(label="Average Self-Sufficiency Ratio", value=f"{avg_ratio:.2f}")

        with col2:
            avg_growth = latest_data["production_growth_rate"].mean()
            st.metric(label="Average Production Growth Rate", value=f"{avg_growth:.2%}")

        with col3:
            total_production = latest_data["total_cereal_production"].sum()
            st.metric(label="Total Cereal Production (tonnes)", value=f"{total_production/1e9:.2f}B tonnes")
            
        at_risk_countries = latest_data[latest_data["self_sufficiency_ratio"] < 0.5]
        if not at_risk_countries.empty:
            st.subheader("Countries at Risk of Food Insecurity (Self-Sufficiency Ratio < 0.5)")
            fig = px.bar(
                at_risk_countries.nsmallest(20, "self_sufficiency_ratio"),
                x="country", 
                y="self_sufficiency_ratio", 
                title=f"Countries with Low Self-Sufficiency in {latest_year}",
                labels={"country": "Country", "self_sufficiency_ratio": "Self-Sufficiency Ratio"},
                color="self_sufficiency_ratio",
                color_continuous_scale="Reds_r"
            )
            st.plotly_chart(fig, use_container_width=True)

        selected_countries = st.multiselect(
            "Select Countries to View Food Security Trends", 
            options=food_security_data["country"].unique(), 
            default=food_security_data["country"].unique()[:5]
        )
        
        if selected_countries:
            filtered_data = food_security_data[food_security_data["country"].isin(selected_countries)]
            fig = px.line(
                filtered_data, 
                x="year", 
                y="self_sufficiency_ratio", 
                color="country", 
                title="Self-Sufficiency Ratio Trends Over Time",
                labels={"year": "Year", "self_sufficiency_ratio": "Self-Sufficiency Ratio", "country": "Country"}
            )
            st.plotly_chart(fig, use_container_width=True)
        
with tab4:
    st.header("Key Insights")
    
    food_security_data = load_table("gold.food_security")
    trade_balance_data = load_table("gold.trade_balance")
    
    if not food_security_data.empty and not trade_balance_data.empty:
        latest_year = food_security_data["year"].max()
        
        st.subheader("Summary Statistics")
        
        latest_food_security = food_security_data[food_security_data["year"] == latest_year]
        
        high_risk_countries = latest_food_security[latest_food_security["self_sufficiency_ratio"] < 0.5]
        moderate_risk_countries = latest_food_security[(latest_food_security["self_sufficiency_ratio"] >= 0.5) & (latest_food_security["self_sufficiency_ratio"] < 0.8)]
        low_risk_countries = latest_food_security[latest_food_security["self_sufficiency_ratio"] >= 0.8]
        
        fig = go.Figure(data=[
            go.Pie(
                labels=["High Risk (<0.5)", "Moderate Risk (0.5-0.8)", "Low Risk (>0.8)"],
                values=[len(high_risk_countries), len(moderate_risk_countries), len(low_risk_countries)],
                hole=0.4,
                marker_colors=["#d62728", "#ff7f0e", "#2ca02c"]
            )
        ])
        fig.update_layout(title=f"Global Food Security Risk Distribution in {latest_year}")
        st.plotly_chart(fig, use_container_width=True)
        
        declining_countries = latest_food_security[latest_food_security["production_growth_rate"] < 0]
        if not declining_countries.empty:
            st.warning(f"{len(declining_countries)} countries have experienced a significant decline in cereal production growth rate (< -5%) in {latest_year}.")
            st.dataframe(declining_countries[["country", "production_growth_rate"]].sort_values("production_growth_rate").head(20))
            
            
