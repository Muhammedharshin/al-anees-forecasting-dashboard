import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# ============================================================
# CONFIG
# ============================================================
API_BASE_URL = "https://al-anees-forecasting-api.onrender.com"   # ← updated to permanent Render URL

st.set_page_config(
    page_title="AL ANEES Demand Forecasting",
    page_icon="📦",
    layout="wide"
)

# ============================================================
# SCREEN 2: DEMAND FORECAST PER SKU
# ============================================================
if screen == "Demand Forecast":
    st.title("📈 Demand Forecast")
    st.caption("Actual vs. predicted weekly units sold, by SKU")

    risk_data = call_api("/api/stockout-risk")
    all_skus = sorted([row["item_no"] for row in risk_data["data"]])

    selected_sku = st.selectbox("Select a SKU", all_skus)

    if selected_sku:
        forecast = call_api(f"/api/forecast/{selected_sku}")
        df = pd.DataFrame(forecast["data"])

        badge = "✅ Prophet + Ensemble available" if forecast["has_prophet_model"] else "ℹ️ XGBoost only (not in top-30 Prophet set)"
        st.info(f"**{selected_sku}** — Primary model: **{forecast['primary_model'].upper()}**  |  {badge}")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["week"], y=df["units_sold"], mode="lines+markers",
                                  name="Actual", line=dict(color="#21295C", width=3)))
        fig.add_trace(go.Scatter(x=df["week"], y=df["xgb_pred"], mode="lines+markers",
                                  name="XGBoost Prediction", line=dict(color="#065A82", width=2, dash="dot")))
        if forecast["has_prophet_model"]:
            fig.add_trace(go.Scatter(x=df["week"], y=df["prophet_pred"], mode="lines+markers",
                                      name="Prophet Prediction", line=dict(color="#1C7293", width=2, dash="dot")))
            fig.add_trace(go.Scatter(x=df["week"], y=df["ensemble_pred"], mode="lines+markers",
                                      name="Ensemble Prediction", line=dict(color="#D98C00", width=2, dash="dot")))

        fig.update_layout(
            xaxis_title="Week", yaxis_title="Units Sold",
            height=450, hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Raw forecast data")
        st.dataframe(df, use_container_width=True, hide_index=True)

# ============================================================
# SCREEN 3: STOCKOUT RISK MONITOR
# ============================================================
if screen == "Stockout Risk Monitor":
    st.title("🚦 Stockout Risk Monitor")
    st.caption("SKUs flagged by risk level, based on current stock and forecasted demand")

    risk_filter = st.radio("Filter by risk level", ["ALL", "RED", "AMBER", "GREEN"], horizontal=True)

    if risk_filter == "ALL":
        risk_data = call_api("/api/stockout-risk")
    else:
        risk_data = call_api("/api/stockout-risk", params={"risk_level": risk_filter})

    summary = risk_data["summary"]
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 RED", summary.get("RED", 0))
    c2.metric("🟠 AMBER", summary.get("AMBER", 0))
    c3.metric("🟢 GREEN", summary.get("GREEN", 0))

    st.divider()

    df = pd.DataFrame(risk_data["data"])
    if not df.empty:
        def highlight_risk(row):
            color = {"RED": "#FDEDEC", "AMBER": "#FFF4E0", "GREEN": "#E8F5EE"}.get(row["risk_level"], "")
            return [f"background-color: {color}"] * len(row)

        display_cols = ["item_no", "brand", "category", "current_stock", "forecasted_demand_wk",
                         "days_of_stock", "recommended_order", "risk_level", "risk_score"]
        styled = df[display_cols].style.apply(highlight_risk, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.warning("No SKUs match this filter.")

# ============================================================
# SCREEN 4: REPLENISHMENT PLANNER
# ============================================================
if screen == "Replenishment Planner":
    st.title("📋 Replenishment Planner")
    st.caption("Recommended order quantities, ready to export")

    needs_order_only = st.checkbox("Show only SKUs that need ordering", value=True)
    repl = call_api("/api/replenishment", params={"needs_order_only": needs_order_only})

    c1, c2, c3 = st.columns(3)
    c1.metric("Total SKUs", repl["total_skus"])
    c2.metric("SKUs Needing Order", repl["skus_needing_order"])
    c3.metric("Total Units to Order", f"{repl['total_units_to_order']:,}")

    st.divider()

    df = pd.DataFrame(repl["data"])
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Excel export
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Replenishment Plan")
        buffer.seek(0)

        st.download_button(
            label="⬇️ Download as Excel",
            data=buffer,
            file_name="replenishment_plan.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No SKUs currently need ordering.")
