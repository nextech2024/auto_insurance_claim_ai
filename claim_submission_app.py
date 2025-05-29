import streamlit as st
import datetime
import json
import boto3
from io import BytesIO
from botocore.exceptions import NoCredentialsError
import random
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Claim Submission", layout="centered")
st.title("🚗 AI-Powered Auto Insurance Claim Submission")

# --- Upload to S3
def upload_to_s3(file_data, filename, bucket="auto-insurance-claims-images-2025"):
    try:
        s3 = boto3.client('s3')
        s3.upload_fileobj(file_data, bucket, filename)
        return f"https://{bucket}.s3.amazonaws.com/{filename}"
    except NoCredentialsError:
        return "❌ AWS credentials not found."

# --- Load claim history
@st.cache_data
def load_history():
    return pd.read_csv("claims_history.csv")

# --- Damage Detection Simulation
def detect_damage(uploaded_image):
    damage_types = ["Rear Bumper", "Front Bumper", "Left Door", "Right Door", "Hood", "Windshield"]
    severity_levels = ["Minor", "Moderate", "Major"]
    return {
        "damage_type": random.choice(damage_types),
        "severity": random.choice(severity_levels)
    }

# --- Fraud Detection Logic
def calculate_risk_score(claim, history_df):
    score = 0
    reasons = []

    same_vin = history_df[history_df['vin'] == claim['vin']]
    if not same_vin.empty:
        score += 30
        reasons.append("Previous claims exist for same VIN")

    recent_claims = same_vin[
        pd.to_datetime(same_vin['claim_date']) >= datetime.datetime.now() - pd.Timedelta(days=180)
    ]
    if len(recent_claims) >= 2:
        score += 40
        reasons.append("Multiple recent claims within 6 months")

    matching_damage = same_vin[same_vin['damage_type'] == claim['damage_type']]
    if not matching_damage.empty:
        score += 20
        reasons.append("Similar damage type in past claims")

    if score > 80:
        score = 80 + min(20, len(reasons) * 5)

    return min(score, 100), reasons

# --- Save to DynamoDB
def save_to_dynamodb(report):
    item = {
        "claim_id": str(report.get("claim_id", "UNKNOWN")),
        "vin": str(report.get("vin", "UNKNOWN")),
        "policy_number": str(report.get("policy_number", "UNKNOWN")),
        "claim_date": str(report.get("claim_date", "")),
        "image_url": str(report.get("image_url", "")),
        "damage_detected": json.dumps(report.get("damage_detected", {})),
        "fraud_detected": json.dumps(report.get("fraud_detected", {}))
    }
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table("ClaimReports")
    table.put_item(Item=item)

# --- Send Email via SES
def send_email_via_ses(subject, body, sender, recipient):
    ses = boto3.client('ses', region_name="us-east-1")
    ses.send_email(
        Source=sender,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}}
        }
    )

# --- Streamlit UI
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
        uploaded_image.seek(0)
        image_bytes = uploaded_image.read()
        image_file_for_s3 = BytesIO(image_bytes)
        image_url = upload_to_s3(image_file_for_s3, uploaded_image.name)

        st.image(image_bytes, caption="Uploaded Damage Image", use_container_width=True)
        st.markdown(f"📷 Image uploaded to S3: [{image_url}]({image_url})")

        claim = {
            "claim_id": claim_id,
            "vin": vin,
            "claim_date": str(claim_date),
            "damage_type": "Unknown"
        }

        damage_result = detect_damage(uploaded_image)
        claim["damage_type"] = damage_result["damage_type"]
        history_df = load_history()
        risk_score, reasons = calculate_risk_score(claim, history_df)
        is_fraud = risk_score >= 70

        combined_result = {
            "claim_id": claim_id,
            "vin": vin,
            "policy_number": policy_number,
            "claim_date": str(claim_date),
            "image_url": image_url,
            "damage_detected": damage_result,
            "fraud_detected": {
                "is_fraud": is_fraud,
                "risk_score": risk_score,
                "reason": reasons
            }
        }

        try:
            save_to_dynamodb(combined_result)
            st.success("✅ Claim report saved to DynamoDB.")
        except Exception as e:
            st.error(f"❌ Failed to save to DynamoDB: {e}")

        try:
            send_email_via_ses(
                subject=f"Claim Report for {claim_id}",
                body = f"""\
Claim Submission Summary

✔ Claim ID: {claim_id}
✔ VIN: {vin}
✔ Policy Number: {policy_number}
✔ Claim Date: {claim_date}
✔ Image URL: {image_url}

🧚 AI Damage Assessment:
- Damage Type: {damage_result['damage_type']}
- Severity: {damage_result['severity']}

🔎 Claim Risk Insights:
- Risk Score: {risk_score}
- Risk Factors:
  {chr(10).join(f"- {r}" for r in reasons)}

Thank you for submitting your claim. A claims specialist will review it and contact you within 24 hours.
""",

                sender="sales@nextech-usa.com",
                recipient="aqeelqureshi@yahoo.com"
            )
            st.success("📧 Email sent successfully!")
        except Exception as e:
            st.error(f"❌ Email failed: {e}")

        # ✅ Final output for policyholder only
        st.markdown("---")
        st.header("✅ Claim Submitted")
        st.success("Thank you for submitting your claim.")
        st.info("Your claim is under review. A claims specialist will contact you within 24 hours.")
