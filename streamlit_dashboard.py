import streamlit as st
import json
import pandas as pd
import random
from datetime import datetime
from PIL import Image
import boto3
from botocore.exceptions import NoCredentialsError
from io import BytesIO
import plotly.express as px

# ------------------ Streamlit Setup ------------------
st.set_page_config(page_title="Auto Insurance Claim", layout="centered")
st.title("🚗 AI-Powered Auto Insurance Claim Submission")
st.write("🚀 App has started...")  # ✅ Debug line

# ------------------ Upload to S3 ------------------
def upload_to_s3(file_data, filename, bucket="auto-insurance-claims-images-2025"):
    try:
        s3 = boto3.client('s3')
        s3.upload_fileobj(file_data, bucket, filename)
        return f"https://{bucket}.s3.amazonaws.com/{filename}"
    except NoCredentialsError:
        return "❌ AWS credentials not found."

# ------------------ Load Claim History ------------------
@st.cache_data
def load_history():
    return pd.read_csv("claims_history.csv")

# ------------------ Simulated Damage Detection ------------------
def detect_damage(uploaded_image):
    damage_types = ["Rear Bumper", "Front Bumper", "Left Door", "Right Door", "Hood", "Windshield"]
    severity_levels = ["Minor", "Moderate", "Major"]
    return {
        "damage_type": random.choice(damage_types),
        "severity": random.choice(severity_levels)
    }

# ------------------ Fraud Detection ------------------
def calculate_risk_score(claim, history_df):
    score = 0
    reasons = []

    same_vin = history_df[history_df['vin'] == claim['vin']]
    if not same_vin.empty:
        score += 30
        reasons.append("Previous claims exist for same VIN")

    recent_claims = same_vin[
        pd.to_datetime(same_vin['claim_date']) >= datetime.now() - pd.Timedelta(days=180)
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

# ------------------ Save to DynamoDB ------------------
def save_to_dynamodb(report):
    try:
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
        st.success("✅ Claim report saved to DynamoDB.")
    except Exception as e:
        st.error(f"❌ Failed to save to DynamoDB: {e}")

# ------------------ Send Email via SES ------------------
def send_email_via_ses(subject, body, sender, recipient):
    try:
        ses = boto3.client('ses', region_name="us-east-1")
        ses.send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}}
            }
        )
        st.success("📧 Email sent successfully!")
    except Exception as e:
        st.error(f"❌ Failed to send email: {e}")

# ------------------ Claim Submission UI ------------------
with st.form("claim_form"):
    st.subheader("📋 Claim Information")
    claim_id = st.text_input("Claim ID", "CLM999")
    vin = st.text_input("Vehicle VIN", "1HGCM82633A004352")
    policy_number = st.text_input("Insurance Policy #", "P-123456789")
    claim_date = st.date_input("Claim Date", datetime.today())
    uploaded_image = st.file_uploader("📷 Upload Damage Photo", type=["jpg", "jpeg", "png"])
    submitted = st.form_submit_button("Submit Claim")

# ------------------ Handle Submission ------------------
if submitted:
    if uploaded_image is None:
        st.error("⚠️ Please upload a damage photo.")
    else:
        st.success("✅ Claim Submitted!")

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

        save_to_dynamodb(combined_result)

        with open("final_claim_result.json", "w") as f:
            json.dump(combined_result, f, indent=2)

        send_email_via_ses(
            subject=f"Claim Report for {claim_id}",
            body=json.dumps(combined_result, indent=2),
            sender="sales@nextech-usa.com",
            recipient="aqeelqureshi@yahoo.com"
        )

        st.subheader("🧚 AI Prediction Result")
        st.write(f"**Damage Type:** {damage_result['damage_type']}")
        st.write(f"**Severity:** {damage_result['severity']}")

        st.subheader("🛡️ Fraud Analysis")
        st.write(f"**Fraud Suspected:** {'Yes' if is_fraud else 'No'}")
        st.write(f"**Risk Score:** {risk_score}")
        st.write("**Reasons:**")
        for r in reasons:
            st.write(f"- {r}")

        # --- Timeline of Claims ---
        st.subheader("📅 Timeline of Claims")

        def extract_fraud(row):
            try:
                if "fraud_detected" in row and pd.notna(row["fraud_detected"]):
                    return "Yes" if json.loads(row["fraud_detected"])["is_fraud"] else "No"
                else:
                    return "Unknown"
            except Exception:
                return "Unknown"

        history_df["Claim Date"] = pd.to_datetime(history_df["claim_date"], errors="coerce")
        history_df["Fraud"] = history_df.apply(extract_fraud, axis=1)

        timeline_fig = px.histogram(
            history_df,
            x="Claim Date",
            color="Fraud",
            nbins=30,
            title="📊 Claims Over Time"
        )
        st.plotly_chart(timeline_fig, use_container_width=True)

# ------------------ Optional main check ------------------
if __name__ == "__main__":
    pass
