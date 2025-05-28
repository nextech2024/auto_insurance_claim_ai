import streamlit as st
import datetime

st.set_page_config(page_title="Claim Submission", layout="centered")
st.title("🚗 AI-Powered Auto Insurance Claim Submission")

with st.form("claim_form"):
    st.subheader("📋 Claim Information")
    claim_id = st.text_input("Claim ID", "CLM999")
    vin = st.text_input("Vehicle VIN", "1HGCM82633A004352")
    policy_number = st.text_input("Insurance Policy #", "P-123456789")
    claim_date = st.date_input("Claim Date", datetime.date.today())
    uploaded_image = st.file_uploader("📷 Upload Damage Photo", type=["jpg", "jpeg", "png"])
    submitted = st.form_submit_button("Submit Claim")

if submitted:
    if uploaded_image is None:
        st.error("⚠️ Please upload a damage photo.")
    else:
        st.success("✅ Claim Submitted Successfully!")
        st.image(uploaded_image, caption="Damage Photo", use_container_width=True)
        st.write(f"**Claim ID:** {claim_id}")
        st.write(f"**VIN:** {vin}")
        st.write(f"**Policy #:** {policy_number}")
        st.write(f"**Claim Date:** {claim_date}")



@app.get("/")
def home():
    return {"message": "🚗 Auto Insurance AI API is running!"}