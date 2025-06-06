import streamlit as st
import boto3
import pandas as pd
import json
import plotly.express as px

# -----------------------------
# 🔄 Manual Refresh
# -----------------------------
st.set_page_config(page_title="Claim Dashboard", layout="wide")
st.title("📊 AI-Powered Auto Insurance Claim Dashboard")

# Add a Refresh Button
if st.button("🔄 Refresh Claims Table"):
    st.rerun()

# -----------------------------
# 📦 Load from DynamoDB
# -----------------------------
def load_claims_from_dynamodb():
    session = boto3.Session(
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=st.secrets["AWS_REGION"]
    )

    dynamodb = session.resource('dynamodb')
    table = dynamodb.Table(st.secrets["DYNAMODB_TABLE_NAME"])

    response = table.scan()
    items = response.get("Items", [])
    claims = []

    for item in items:
        try:
            damage = json.loads(item["damage_detected"])
            fraud = json.loads(item["fraud_detected"])
            claims.append({
                "Claim ID": item["claim_id"],
                "VIN": item["vin"],
                "Policy": item["policy_number"],
                "Date": item["claim_date"],
                "Damage Type": damage.get("damage_type", "Unknown"),
                "Severity": damage.get("severity", "Unknown"),
                "Risk Score": fraud.get("risk_score", 0),
                "Fraud": "Yes" if fraud.get("is_fraud") else "No"
            })
        except Exception as e:
            st.warning(f"Error parsing claim: {e}")

    return pd.DataFrame(claims)


# -----------------------------
# 📊 Build Dashboard
# -----------------------------
df = load_claims_from_dynamodb()

# ✅ Optional Filters
st.sidebar.header("🔍 Filter Claims")

# Damage Type Filter
damage_types = df["Damage Type"].unique().tolist()
selected_damage = st.sidebar.multiselect("Filter by Damage Type", damage_types, default=damage_types)

# Fraud Status Filter
fraud_status = df["Fraud"].unique().tolist()
selected_fraud = st.sidebar.multiselect("Filter by Fraud Status", fraud_status, default=fraud_status)

# Date Range Filter
df["Date"] = pd.to_datetime(df["Date"])
min_date = df["Date"].min()
max_date = df["Date"].max()
start_date, end_date = st.sidebar.date_input("Filter by Date Range", [min_date, max_date])

# Apply filters
filtered_df = df[
    (df["Damage Type"].isin(selected_damage)) &
    (df["Fraud"].isin(selected_fraud)) &
    (df["Date"] >= pd.to_datetime(start_date)) &
    (df["Date"] <= pd.to_datetime(end_date))
]

# -----------------------------
# 📈 Visuals
# -----------------------------
if filtered_df.empty:
    st.info("No claims found for the selected filters.")
else:
    st.metric("Total Claims", len(filtered_df))

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔧 Claims by Damage Type")
        damage_counts = filtered_df["Damage Type"].value_counts().reset_index()
        damage_counts.columns = ["Damage Type", "Count"]
        damage_fig = px.bar(damage_counts, x="Damage Type", y="Count")
        st.plotly_chart(damage_fig, use_container_width=True)

    with col2:
        st.subheader("🛡️ Fraud Risk Distribution")
        fraud_fig = px.pie(filtered_df, names="Fraud", title="Fraud vs. Legitimate Claims")
        st.plotly_chart(fraud_fig, use_container_width=True)

    st.subheader("📅 Claims Over Time")
    timeline_fig = px.histogram(filtered_df, x="Date", nbins=20)
    st.plotly_chart(timeline_fig, use_container_width=True)

    st.subheader("📋 Raw Claim Data")
    st.dataframe(filtered_df)
