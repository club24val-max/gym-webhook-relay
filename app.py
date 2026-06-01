from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime
import pytz

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

REPLIFY_API_KEY_OLD = "KZ3RAX9xJmzmLZJGMcOt4zDx94rHQd89fnlLTFEj"
REPLIFY_API_KEY_NEW = "D0SNMBdfhl7XbBdu4jUdk8TB85AxDj4r6YZ77lVL"
BASE_URL = "https://api.heylibby.com/api/v1/campaigns/{campaign_id}/contacts"
OUTBOUND_URL = "https://api.heylibby.com/api/v1/outbound/call"
EASTERN = pytz.timezone("America/New_York")

AGENT_IDS = {
    "wallingford":  "a2c02d50-4f11-4311-b359-3ca89028df57",
    "torrington":   "437c8652-988a-4354-a03f-40245c8822c4",
    "ridgefield":   "0c0d6b76-7e35-41e0-a36b-7106f6c2fda1",
    "newtown":      "dea52645-a68d-4203-85cc-dbfda35b3796",
    "newmilford":   "2500aaa6-a255-4ae3-8c82-ee8a6aaf6b43",
    "middletown":   "60cb543e-4663-45be-a968-71f291e13a49",
    "brookfield":   "acc93743-938c-4637-814a-4dc9feafa175",
}

GYMS = {
    # --- Week Trial (outbound call API) ---
    "wallingford":  {"type": "outbound", "gym": "wallingford", "campaign": "weektrial"},
    "torrington":   {"type": "outbound", "gym": "torrington", "campaign": "weektrial"},
    "ridgefield":   {"type": "outbound", "gym": "ridgefield", "campaign": "weektrial"},
    "newtown":      {"type": "outbound", "gym": "newtown", "campaign": "weektrial"},
    "newmilford":   {"type": "outbound", "gym": "newmilford", "campaign": "weektrial"},
    "middletown":   {"type": "outbound", "gym": "middletown", "campaign": "weektrial"},
    "brookfield":   {"type": "outbound", "gym": "brookfield", "campaign": "weektrial"},

    # --- Toured / No Join (outbound call API) ---
    "wallingford-toured":  {"type": "outbound", "gym": "wallingford", "campaign": "toured"},
    "torrington-toured":   {"type": "outbound", "gym": "torrington", "campaign": "toured"},
    "ridgefield-toured":   {"type": "outbound", "gym": "ridgefield", "campaign": "toured"},
    "newtown-toured":      {"type": "outbound", "gym": "newtown", "campaign": "toured"},
    "newmilford-toured":   {"type": "outbound", "gym": "newmilford", "campaign": "toured"},
    "middletown-toured":   {"type": "outbound", "gym": "middletown", "campaign": "toured"},
    "brookfield-toured":   {"type": "outbound", "gym": "brookfield", "campaign": "toured"},

    # --- Cancelled Member Month 1 (outbound call API) ---
    "wallingford-cancelled-month1":  {"type": "outbound", "gym": "wallingford", "campaign": "cancelled-month1"},
    "torrington-cancelled-month1":   {"type": "outbound", "gym": "torrington", "campaign": "cancelled-month1"},
    "ridgefield-cancelled-month1":   {"type": "outbound", "gym": "ridgefield", "campaign": "cancelled-month1"},
    "newtown-cancelled-month1":      {"type": "outbound", "gym": "newtown", "campaign": "cancelled-month1"},
    "newmilford-cancelled-month1":   {"type": "outbound", "gym": "newmilford", "campaign": "cancelled-month1"},
    "middletown-cancelled-month1":   {"type": "outbound", "gym": "middletown", "campaign": "cancelled-month1"},
    "brookfield-cancelled-month1":   {"type": "outbound", "gym": "brookfield", "campaign": "cancelled-month1"},

    # --- Cancelled Member Month 2 (outbound call API) ---
    "wallingford-cancelled-month2":  {"type": "outbound", "gym": "wallingford", "campaign": "cancelled-month2"},
    "torrington-cancelled-month2":   {"type": "outbound", "gym": "torrington", "campaign": "cancelled-month2"},
    "ridgefield-cancelled-month2":   {"type": "outbound", "gym": "ridgefield", "campaign": "cancelled-month2"},
    "newtown-cancelled-month2":      {"type": "outbound", "gym": "newtown", "campaign": "cancelled-month2"},
    "newmilford-cancelled-month2":   {"type": "outbound", "gym": "newmilford", "campaign": "cancelled-month2"},
    "middletown-cancelled-month2":   {"type": "outbound", "gym": "middletown", "campaign": "cancelled-month2"},
    "brookfield-cancelled-month2":   {"type": "outbound", "gym": "brookfield", "campaign": "cancelled-month2"},

    # --- Cancelled Member Month 3 (outbound call API) ---
    "wallingford-cancelled-month3":  {"type": "outbound", "gym": "wallingford", "campaign": "cancelled-month3"},
    "torrington-cancelled-month3":   {"type": "outbound", "gym": "torrington", "campaign": "cancelled-month3"},
    "ridgefield-cancelled-month3":   {"type": "outbound", "gym": "ridgefield", "campaign": "cancelled-month3"},
    "newtown-cancelled-month3":      {"type": "outbound", "gym": "newtown", "campaign": "cancelled-month3"},
    "newmilford-cancelled-month3":   {"type": "outbound", "gym": "newmilford", "campaign": "cancelled-month3"},
    "middletown-cancelled-month3":   {"type": "outbound", "gym": "middletown", "campaign": "cancelled-month3"},
    "brookfield-cancelled-month3":   {"type": "outbound", "gym": "brookfield", "campaign": "cancelled-month3"},

    # --- Past Due 0-30 (old API key) ---
    "wallingford-pastdue0-30":  "cdc2306a-9f8c-4da0-85fd-62d890740137",
    "torrington-pastdue0-30":   "90f8c7c3-5a48-4499-a2f5-1e1b7383f592",
    "ridgefield-pastdue0-30":   "3cbfe5e4-8521-447c-a7e3-795b10aa8467",
    "newtown-pastdue0-30":      "2684b8ea-3c87-413e-89cd-83fc22405287",
    "newmilford-pastdue0-30":   "0681a240-4771-43ba-b0ea-539e9dc760ab",
    "middletown-pastdue0-30":   "97391e22-f568-473f-a234-3f4c978f0e25",
    "brookfield-pastdue0-30":   "3fddf132-90fb-4b1c-b287-19d6468478bb",

    # --- Past Due 31-60 (old API key) ---
    "wallingford-pastdue31-60": "bead3dd7-4bad-4a8d-8862-7a057acf069a",
    "torrington-pastdue31-60":  "a85aa596-0c39-4d45-b119-a9ce09a26460",
    "ridgefield-pastdue31-60":  "8b581d95-4287-4cfc-a4cf-7e533c24dc22",
    "newtown-pastdue31-60":     "94d1f0ee-c4fb-4887-8dc7-b69df1c99157",
    "newmilford-pastdue31-60":  "08ce2214-369c-4a12-8416-56a46e32200d",
    "middletown-pastdue31-60":  "447b3a5a-0dfd-42ff-a5b4-164ab820e0d5",
    "brookfield-pastdue31-60":  "63aa4d47-7428-48f9-bff2-8124b16686fc",

    # --- Past Due 61-90 (old API key) ---
    "wallingford-pastdue61-90": "128f0096-de10-43a5-82d0-f92f668bacd0",
    "torrington-pastdue61-90":  "216579c4-de5d-49dd-b105-83293b3c3e18",
    "ridgefield-pastdue61-90":  "4f968f09-a704-4245-9223-653804e14e9c",
    "newtown-pastdue61-90":     "e662751d-a7e7-4cdf-a60b-bb6ef92aaad3",
    "newmilford-pastdue61-90":  "7b019ef7-de80-4746-b39a-ff20defc57b7",
    "middletown-pastdue61-90":  "fadc497d-5375-434e-8c4d-a2c037ada327",
    "brookfield-pastdue61-90":  "6a5dfefc-94cd-42ca-9b82-5bdfb8bc52d1",

    # --- PT Past Due 0-30 (old API key) ---
    "wallingford-ptpastdue0-30":  "40b4abcd-f2fc-4487-9d28-3e98bc6acfd2",
    "torrington-ptpastdue0-30":   "c8820391-9be2-40ee-bb12-7fe974a0d89d",
    "ridgefield-ptpastdue0-30":   "10a65701-cc63-4bc3-bfd8-6f335c5ee531",
    "newtown-ptpastdue0-30":      "2b03f651-88ed-4ed1-9cba-344743da47a7",
    "newmilford-ptpastdue0-30":   "6c2e6259-1d19-4c98-98bc-01ecaac8901c",
    "middletown-ptpastdue0-30":   "538923b0-acaa-41d7-8cd2-86fde68e6769",
    "brookfield-ptpastdue0-30":   "55565835-d297-4c5b-b4f5-d9ca51245fa9",

    # --- PT Past Due 31-60 (old API key) ---
    "wallingford-ptpastdue31-60": "6b5200f0-cf2a-4353-868e-2083e1fc3955",
    "torrington-ptpastdue31-60":  "2c9c3fc2-e575-4a1c-b788-4af5a87aa656",
    "ridgefield-ptpastdue31-60":  "337f4b83-1836-49db-9b0f-dee5fbd78c01",
    "newtown-ptpastdue31-60":     "5fbf5606-15a8-40a0-924e-da21234f9481",
    "newmilford-ptpastdue31-60":  "06a91e4c-2ed2-48ac-ad95-c5438b267af9",
    "middletown-ptpastdue31-60":  "efbd172e-0087-4ea9-9e78-09f3b8b0682d",
    "brookfield-ptpastdue31-60":  "367cc250-e51c-4c6a-ab50-11a5bfe64977",

    # --- PT Past Due 61-90 (old API key) ---
    "wallingford-ptpastdue61-90": "7b4264e6-e409-4210-9708-b3e7dc27d485",
    "torrington-ptpastdue61-90":  "9b6a1dc2-570a-45c0-8cc9-8e3dbe4cf9b7",
    "ridgefield-ptpastdue61-90":  "b5b6abae-95e8-4cf6-97b4-9defc2840274",
    "newtown-ptpastdue61-90":     "25f4113f-8854-430b-b737-00edad1b62c2",
    "newmilford-ptpastdue61-90":  "be4ead7c-6a1a-4ca3-a9a1-6043bcb7d0f6",
    "middletown-ptpastdue61-90":  "745714c3-76d2-4cf5-806d-8661d95f4a49",
    "brookfield-ptpastdue61-90":  "02ac7b55-4430-4062-91d1-b43d6bd8c3ef",
}

INTRO_MESSAGES = {
    "weektrial": "Hi {first_name}, this is Maya calling from Club 24. I saw you recently claimed your free 7-day pass, and I wanted to personally welcome you and help you get started. We'd love to get your first workout scheduled so you can take full advantage of your free week. What day works best for you to come in and check out the club?",
    "toured": "Hi {first_name}, this is Maya calling from Club 24. You toured our facility a couple of weeks ago, and I just wanted to follow up to see if you had any questions about membership or the club itself. We're also currently offering a special promotion exclusively for recent tour guests, and I wanted to make sure you had the opportunity to take advantage of it before it ends. Do you have any questions for us?",
    "cancelled-month1": "Hey {first_name}, this is Ashley over at Club 24. I know it's been about a month since you canceled your membership, and I just wanted to check in real quick because we hadn't seen you around. Usually when members step away it's because schedules change, work gets hectic, or life just gets busy for a bit — totally understandable. I was curious… have you still been able to stay active lately?",
    "cancelled-month2": "Hey {first_name}, this is Ashley over at Club 24. I know it's been a couple months since you canceled your membership, and I wanted to reach out because we've actually been helping a lot of former members restart their routines recently. A lot of people tell us once they fall out of rhythm, it gets harder and harder to get back into it — so I figured I'd check in and see how things have been going for you lately.",
    "cancelled-month3": "Hey {first_name}, this is Ashley over at Club 24. I know it's been a few months since you were last with us, but I wanted to reach out one more time because we're wrapping up a special restart opportunity for former members. Honestly, a lot of people wait for the 'perfect time' to get back into a routine — and then months turn into a year really fast. So I just wanted to see if restarting your fitness routine was something you'd still be open to exploring.",
}

VOICEMAIL_MESSAGES = {
    "weektrial": "Hi {first_name}, this is Maya calling from Club 24. I'm reaching out because you recently signed up for a free 7-day pass with us. I wanted to help you get your first visit scheduled and answer any questions you may have before coming in. Give us a call back, and we'll get your free week started. We look forward to seeing you soon!",
    "toured": "Hi {first_name}, this is Maya calling from Club 24. I'm just following up regarding your recent visit and tour at our facility a couple of weeks ago. I wanted to check in to see if you had any questions about membership options and also let you know we currently have a special promotion available exclusively for recent tour guests for a limited time. Please give us a call back, go to our website club24gyms dot com, or stop by the club anytime. We'd love to help you get started. Thanks again, and we look forward to hearing from you soon.",
    "cancelled-month1": "Hey {first_name}, this is Ashley over at Club 24. I just wanted to reach out and check in since it's been about a month since your membership ended. We've been reconnecting with some former members lately, and your name came up. No rush at all, but if you've thought about getting back into a routine, give us a quick call back. Again, this is Ashley over at Club 24. Hope to hear from you soon.",
    "cancelled-month2": "Hey {first_name}, this is Ashley over at Club 24. I wanted to reach out because we're currently helping a lot of former members get restarted, and I thought it might be a good time to check in with you too. We do have a simple return-member option available right now if getting back into a routine has been on your mind at all. Give me a call back. Again, this is Ashley at Club 24.",
    "cancelled-month3": "Hey {first_name}, this is Ashley over at Club 24. I wanted to give you one last quick call because we're wrapping up a return-member opportunity for former members, and I didn't want you to miss it if getting back into a routine was something you were considering. If you want to reconnect or hear the details, give us a quick call back. Again, this is Ashley at Club 24.",
}

def is_within_calling_hours():
    now = datetime.now(EASTERN)
    hour = now.hour
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    if weekday < 5:  # Monday - Friday
        return 9 <= hour < 20
    else:  # Saturday - Sunday
        return 9 <= hour < 18

def make_outbound_call(gym_name, campaign, data):
    if not is_within_calling_hours():
        now = datetime.now(EASTERN)
        logging.info(f"[{gym_name}-{campaign}] Outside calling hours ({now.strftime('%A %I:%M %p ET')}) — call skipped.")
        return type('Response', (), {'status_code': 200, 'text': 'Outside calling hours — call skipped'})()

    first_name = (
        data.get("firstName") or
        data.get("First_name") or
        data.get("first_name") or "there"
    )
    phone = str(data.get("phone") or data.get("Phone") or "")
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not phone.startswith("+"):
        phone = "+1" + phone if len(phone) == 10 else "+" + phone

    agent_id = AGENT_IDS.get(gym_name)
    payload = {
        "agentId": agent_id,
        "contact": {
            "phoneNumber": phone,
            "firstName": data.get("firstName") or data.get("First_name") or "",
            "lastName": data.get("lastName") or data.get("Last_name") or "",
            "email": data.get("email") or data.get("Email") or "",
        },
        "metadata": {
            "gym": gym_name,
            "source": campaign
        },
        "introMessage": INTRO_MESSAGES[campaign].format(first_name=first_name),
        "voicemailMessage": VOICEMAIL_MESSAGES[campaign].format(first_name=first_name),
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": REPLIFY_API_KEY_NEW
    }

    response = requests.post(OUTBOUND_URL, json=payload, headers=headers)
    logging.info(f"[{gym_name}-{campaign}] Outbound call response: {response.status_code} - {response.text}")
    return response

def forward_to_replify(gym_entry, data, gym_name):
    payload = {
        "contacts": [
            {
                "firstName": (
                    data.get("firstName") or
                    data.get("First_name") or
                    data.get("first_name") or ""
                ),
                "lastName": (
                    data.get("lastName") or
                    data.get("Last_name") or
                    data.get("last_name") or ""
                ),
                "email": (
                    data.get("email") or
                    data.get("Email") or ""
                ),
                "phone": (
                    data.get("phone") or
                    data.get("Phone") or ""
                ),
                "contactMetadata": {
                    "source": gym_name,
                    "gym": gym_name.split("-")[0],
                    "pastDueAmount": (
                        data.get("pastdueamount") or
                        data.get("Total_past_due_balance") or ""
                    ),
                    "agreementNumber": (
                        data.get("agreement#") or
                        data.get("Agreement") or ""
                    )
                }
            }
        ],
        "action": "upsert"
    }

    if isinstance(gym_entry, dict) and gym_entry.get("new"):
        campaign_id = gym_entry["campaign_id"]
        api_key = REPLIFY_API_KEY_NEW
    else:
        campaign_id = gym_entry
        api_key = REPLIFY_API_KEY_OLD

    url = BASE_URL.format(campaign_id=campaign_id)
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }

    response = requests.post(url, json=payload, headers=headers)
    logging.info(f"[{gym_name}] Replify response: {response.status_code} - {response.text}")
    return response

@app.route("/webhook/<path:gym_name>", methods=["POST"])
def webhook(gym_name):
    gym_key = gym_name.lower().replace(" ", "")

    if gym_key not in GYMS:
        logging.warning(f"Unknown gym: {gym_name}")
        return jsonify({"error": f"Unknown gym: {gym_name}"}), 404

    gym_entry = GYMS[gym_key]
    if not gym_entry or gym_entry == "":
        logging.warning(f"No campaign ID set for: {gym_name}")
        return jsonify({"error": f"No campaign ID configured for: {gym_name}"}), 400

    data = request.json or request.form.to_dict()
    logging.info(f"[{gym_name}] Received from GleanTap: {data}")

    if isinstance(gym_entry, dict) and gym_entry.get("type") == "outbound":
        response = make_outbound_call(gym_entry["gym"], gym_entry["campaign"], data)
    else:
        response = forward_to_replify(gym_entry, data, gym_name)

    return jsonify({
        "status": "ok",
        "gym": gym_name,
        "replify_status": response.status_code
    }), 200

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "gyms": list(GYMS.keys())
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
