import os
import base64

# Decode GCP credentials and write to temp file
gcp_creds = os.environ.get("GOOGLE_CREDENTIALS_BASE64")
if gcp_creds:
    with open("google-credentials.json", "wb") as f:
        f.write(base64.b64decode(gcp_creds))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-credentials.json"
