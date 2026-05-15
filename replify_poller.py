"""
Replify Campaign Poller
Pulls call outcomes from Replify's internal API and logs them
into the call_analytics.db database.

Runs on a schedule (e.g., every hour via cron or background thread).
Uses Cognito auth to get/refresh Bearer tokens automatically.
"""

import requests
import logging
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytz

from replify_call_outcomes import call_analytics, EASTERN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Replify internal API
CAMPAIGN_API_BASE = "https://campaign.mylibby.ai/campaigns"

# Your Cognito credentials (same login you use for app.replify.ai)
# Set these as environment variables on Render for security
import os
COGNITO_USERNAME = os.environ.get("REPLIFY_USERNAME", "")
COGNITO_PASSWORD = os.environ.get("REPLIFY_PASSWORD", "")

# Cognito pool details (from your browser network tab)
COGNITO_REGION = "us-east-1"
COGNITO_CLIENT_ID = "1rkksfkasrk92m6rec8p5crqc1"
COGNITO_USER_POOL_ID = "us-east-1_er9eUugA0"

# All your campaign IDs (from app.py GYMS dict)
CAMPAIGNS = {
    # --- Week Trial ---
    "wallingford": "06af6ac8-6501-4562-87b5-b546fd61e683",
    "torrington": "87396182-4f0d-4d8d-b996-dfebbf355a3b",
    "ridgefield": "8c5612c3-dce9-4e72-b926-eee2b178006e",
    "newtown": "16e2cb63-1b40-484b-9d1c-561e2c659a35",
    "newmilford": "b819041d-9ac8-41cc-835a-9ecdc4ba9cde",
    "middletown": "526b3220-5831-4da7-b56c-38de83037af5",
    "brookfield": "f5c30a3e-1bb3-4ed4-83b9-7fb80780194f",

    # --- Past Due 0-30 ---
    "wallingford-pastdue0-30": "cdc2306a-9f8c-4da0-85fd-62d890740137",
    "torrington-pastdue0-30": "90f8c7c3-5a48-4499-a2f5-1e1b7383f592",
    "ridgefield-pastdue0-30": "3cbfe5e4-8521-447c-a7e3-795b10aa8467",
    "newtown-pastdue0-30": "2684b8ea-3c87-413e-89cd-83fc22405287",
    "newmilford-pastdue0-30": "0681a240-4771-43ba-b0ea-539e9dc760ab",
    "middletown-pastdue0-30": "97391e22-f568-473f-a234-3f4c978f0e25",
    "brookfield-pastdue0-30": "3fddf132-90fb-4b1c-b287-19d6468478bb",

    # --- Past Due 31-60 ---
    "wallingford-pastdue31-60": "bead3dd7-4bad-4a8d-8862-7a057acf069a",
    "torrington-pastdue31-60": "a85aa596-0c39-4d45-b119-a9ce09a26460",
    "ridgefield-pastdue31-60": "8b581d95-4287-4cfc-a4cf-7e533c24dc22",
    "newtown-pastdue31-60": "94d1f0ee-c4fb-4887-8dc7-b69df1c99157",
    "newmilford-pastdue31-60": "08ce2214-369c-4a12-8416-56a46e32200d",
    "middletown-pastdue31-60": "447b3a5a-0dfd-42ff-a5b4-164ab820e0d5",
    "brookfield-pastdue31-60": "63aa4d47-7428-48f9-bff2-8124b16686fc",

    # --- Past Due 61-90 ---
    "wallingford-pastdue61-90": "128f0096-de10-43a5-82d0-f92f668bacd0",
    "torrington-pastdue61-90": "216579c4-de5d-49dd-b105-83293b3c3e18",
    "ridgefield-pastdue61-90": "4f968f09-a704-4245-9223-653804e14e9c",
    "newtown-pastdue61-90": "e662751d-a7e7-4cdf-a60b-bb6ef92aaad3",
    "newmilford-pastdue61-90": "7b019ef7-de80-4746-b39a-ff20defc57b7",
    "middletown-pastdue61-90": "fadc497d-5375-434e-8c4d-a2c037ada327",
    "brookfield-pastdue61-90": "6a5dfefc-94cd-42ca-9b82-5bdfb8bc52d1",

    # --- PT Past Due 0-30 ---
    "wallingford-ptpastdue0-30": "40b4abcd-f2fc-4487-9d28-3e98bc6acfd2",
    "torrington-ptpastdue0-30": "c8820391-9be2-40ee-bb12-7fe974a0d89d",
    "ridgefield-ptpastdue0-30": "10a65701-cc63-4bc3-bfd8-6f335c5ee531",
    "newtown-ptpastdue0-30": "2b03f651-88ed-4ed1-9cba-344743da47a7",
    "newmilford-ptpastdue0-30": "6c2e6259-1d19-4c98-98bc-01ecaac8901c",
    "middletown-ptpastdue0-30": "538923b0-acaa-41d7-8cd2-86fde68e6769",
    "brookfield-ptpastdue0-30": "55565835-d297-4c5b-b4f5-d9ca51245fa9",

    # --- PT Past Due 31-60 ---
    "wallingford-ptpastdue31-60": "6b5200f0-cf2a-4353-868e-2083e1fc3955",
    "torrington-ptpastdue31-60": "2c9c3fc2-e575-4a1c-b788-4af5a87aa656",
    "ridgefield-ptpastdue31-60": "337f4b83-1836-49db-9b0f-dee5fbd78c01",
    "newtown-ptpastdue31-60": "5fbf5606-15a8-40a0-924e-da21234f9481",
    "newmilford-ptpastdue31-60": "06a91e4c-2ed2-48ac-ad95-c5438b267af9",
    "middletown-ptpastdue31-60": "efbd172e-0087-4ea9-9e78-09f3b8b0682d",
    "brookfield-ptpastdue31-60": "367cc250-e51c-4c6a-ab50-11a5bfe64977",

    # --- PT Past Due 61-90 ---
    "wallingford-ptpastdue61-90": "7b4264e6-e409-4210-9708-b3e7dc27d485",
    "torrington-ptpastdue61-90": "9b6a1dc2-570a-45c0-8cc9-8e3dbe4cf9b7",
    "ridgefield-ptpastdue61-90": "b5b6abae-95e8-4cf6-97b4-9defc2840274",
    "newtown-ptpastdue61-90": "25f4113f-8854-430b-b737-00edad1b62c2",
    "newmilford-ptpastdue61-90": "be4ead7c-6a1a-4ca3-a9a1-6043bcb7d0f6",
    "middletown-ptpastdue61-90": "745714c3-76d2-4cf5-806d-8661d95f4a49",
    "brookfield-ptpastdue61-90": "02ac7b55-4430-4062-91d1-b43d6bd8c3ef",
}

# Map gym names from metadata to club IDs
GYM_TO_CLUB_ID = {
    "wallingford": "09556",
    "torrington": "09557",
    "ridgefield": "09558",
    "newtown": "09559",
    "newmilford": "09560",
    "middletown": "09561",
    "brookfield": "09562",
}


# ============================================================================
# COGNITO AUTH
# ============================================================================

_cached_token = None
_token_expiry = None


def get_auth_token():
    """Get a valid Bearer token using Cognito USER_PASSWORD_AUTH."""
    global _cached_token, _token_expiry

    # Return cached token if still valid
    if _cached_token and _token_expiry and datetime.now() < _token_expiry:
        return _cached_token

    if not COGNITO_USERNAME or not COGNITO_PASSWORD:
        logger.error("REPLIFY_USERNAME and REPLIFY_PASSWORD environment variables not set")
        return None

    try:
        import boto3
        client = boto3.client("cognito-idp", region_name=COGNITO_REGION)

        response = client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": COGNITO_USERNAME,
                "PASSWORD": COGNITO_PASSWORD,
            },
        )

        result = response["AuthenticationResult"]
        _cached_token = result["AccessToken"]
        # Token usually valid for 1 hour; refresh 5 min early
        _token_expiry = datetime.now() + timedelta(seconds=result.get("ExpiresIn", 3600) - 300)

        logger.info("Successfully obtained Cognito auth token")
        return _cached_token

    except ImportError:
        logger.error("boto3 not installed. Run: pip install boto3")
        return None
    except Exception as e:
        logger.error(f"Cognito auth failed: {e}")
        return None


# ============================================================================
# POLL CAMPAIGNS
# ============================================================================

def fetch_campaign_contacts(campaign_id, token, page=1, limit=100):
    """Fetch contacts with call outcomes from a single campaign."""
    url = f"{CAMPAIGN_API_BASE}/{campaign_id}/contacts/paginated"
    params = {
        "page": page,
        "limit": limit,
        "outreachFilter": "all",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 401:
            logger.warning("Token expired, will refresh on next poll")
            global _cached_token, _token_expiry
            _cached_token = None
            _token_expiry = None
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch campaign {campaign_id}: {e}")
        return None


def process_campaign_contacts(data, campaign_name):
    """Process contacts from API response and log outcomes."""
    if not data or "data" not in data:
        return 0

    contacts = data["data"].get("campaignContacts", [])
    logged_count = 0

    for contact in contacts:
        phone = contact.get("phone", "")
        first_name = contact.get("firstName", "")
        last_name = contact.get("lastName", "")
        metadata = contact.get("contactMetadata", {})
        gym_name = metadata.get("gym", "")
        source = metadata.get("source", campaign_name)

        # Get club ID from gym name
        club_id = GYM_TO_CLUB_ID.get(gym_name.lower(), "unknown")

        # Determine campaign type from source
        campaign_type = source if source else campaign_name

        # Process each outreach (call attempt)
        outreach_list = contact.get("Outreach", [])
        for outreach in outreach_list:
            outreach_id = outreach.get("id", "")
            status = outreach.get("status", "").lower()
            channel = outreach.get("channel", "")
            executed_at = outreach.get("executedAt")
            scheduled_for = outreach.get("scheduledFor")

            # Only process phone calls
            if channel != "phone":
                continue

            # Map Replify status to our outcome format
            if status == "answered":
                outcome = "answered"
            elif status == "voicemail":
                outcome = "voicemail"
            elif status in ("noAnswer", "no_answer", "failed", "busy"):
                outcome = "no_answer"
            elif status == "completed":
                outcome = "answered"  # completed usually means answered
            else:
                outcome = "no_answer"  # default for unknown

            # Use outreach ID as unique replify_call_id to prevent duplicates
            replify_call_id = f"replify-{outreach_id}"

            try:
                call_analytics.log_call_outcome(
                    phone=phone,
                    campaign=campaign_type,
                    outcome=outcome,
                    club_id=club_id,
                    replify_call_id=replify_call_id,
                    duration_seconds=0,
                    disposition=status,
                    notes=f"{first_name} {last_name}"
                )
                logged_count += 1
            except Exception as e:
                # Duplicate replify_call_id means we already logged this
                if "UNIQUE constraint" in str(e):
                    pass  # Already logged, skip
                else:
                    logger.error(f"Error logging {phone}: {e}")

    return logged_count


def poll_all_campaigns():
    """Poll all campaigns and log call outcomes."""
    token = get_auth_token()
    if not token:
        logger.error("Cannot poll: no auth token available")
        return

    total_logged = 0
    total_campaigns = len(CAMPAIGNS)

    logger.info(f"Starting poll of {total_campaigns} campaigns...")

    for campaign_name, campaign_id in CAMPAIGNS.items():
        if not campaign_id:
            continue  # Skip empty campaign IDs

        logger.info(f"Polling: {campaign_name} ({campaign_id[:8]}...)")

        page = 1
        while True:
            data = fetch_campaign_contacts(campaign_id, token, page=page, limit=100)
            if not data:
                break

            logged = process_campaign_contacts(data, campaign_name)
            total_logged += logged

            # Check if there are more pages
            total_contacts = data.get("data", {}).get("campaignContactsCount", 0)
            contacts_fetched = len(data.get("data", {}).get("campaignContacts", []))

            if contacts_fetched < 100 or page * 100 >= total_contacts:
                break  # No more pages

            page += 1
            time.sleep(0.5)  # Rate limit: be respectful

        time.sleep(0.5)  # Small delay between campaigns

    logger.info(f"Poll complete. Logged {total_logged} new call outcomes across {total_campaigns} campaigns.")
    return total_logged


# ============================================================================
# FLASK ROUTE - Trigger poll manually or view status
# ============================================================================

from flask import Blueprint, jsonify

poller_bp = Blueprint('poller', __name__, url_prefix='/api/poller')


@poller_bp.route("/run", methods=["POST"])
def trigger_poll():
    """Manually trigger a poll of all campaigns."""
    try:
        count = poll_all_campaigns()
        return jsonify({
            "status": "success",
            "new_outcomes_logged": count,
            "campaigns_polled": len(CAMPAIGNS),
            "timestamp": datetime.now(EASTERN).isoformat()
        })
    except Exception as e:
        logger.error(f"Poll failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@poller_bp.route("/status", methods=["GET"])
def poll_status():
    """Check poller status and auth."""
    has_creds = bool(COGNITO_USERNAME and COGNITO_PASSWORD)
    token_valid = bool(_cached_token and _token_expiry and datetime.now() < _token_expiry)

    return jsonify({
        "credentials_configured": has_creds,
        "token_valid": token_valid,
        "token_expires": _token_expiry.isoformat() if _token_expiry else None,
        "campaigns_configured": len(CAMPAIGNS),
    })


# ============================================================================
# BACKGROUND SCHEDULER (optional - runs poll every hour)
# ============================================================================

def start_background_poller(interval_hours=1):
    """Start a background thread that polls every N hours."""
    import threading

    def _poll_loop():
        while True:
            try:
                logger.info("Background poller: starting poll...")
                poll_all_campaigns()
            except Exception as e:
                logger.error(f"Background poll error: {e}")
            time.sleep(interval_hours * 3600)

    thread = threading.Thread(target=_poll_loop, daemon=True)
    thread.start()
    logger.info(f"Background poller started (every {interval_hours} hour(s))")


# ============================================================================
# STANDALONE: Run directly to test
# ============================================================================

if __name__ == "__main__":
    print("Testing Replify campaign poller...")
    print(f"Credentials configured: {bool(COGNITO_USERNAME)}")
    print(f"Campaigns configured: {len(CAMPAIGNS)}")

    if COGNITO_USERNAME:
        token = get_auth_token()
        if token:
            print(f"Auth token obtained: {token[:20]}...")
            poll_all_campaigns()
        else:
            print("Failed to get auth token")
    else:
        print("Set REPLIFY_USERNAME and REPLIFY_PASSWORD environment variables")
