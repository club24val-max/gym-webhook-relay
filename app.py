from flask import Flask, request, jsonify
import requests
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

REPLIFY_API_KEY = "KZ3RAX9xJmzmLZJGMcOt4zDx94rHQd89fnlLTFEj"
BASE_URL = "https://api.heylibby.com/api/v1/campaigns/{campaign_id}/contacts"

GYMS = {
    # --- Week Trial ---
    "wallingford":              "06af6ac8-6501-4562-87b5-b546fd61e683",
    "torrington":               "87396182-4f0d-4d8d-b996-dfebbf355a3b",
    "ridgefield":               "8c5612c3-dce9-4e72-b926-eee2b178006e",
    "newtown":                  "16e2cb63-1b40-484b-9d1c-561e2c659a35",
    "newmilford":               "b819041d-9ac8-41cc-835a-9ecdc4ba9cde",
    "middletown":               "526b3220-5831-4da7-b56c-38de83037af5",
    "brookfield":               "f5c30a3e-1bb3-4ed4-83b9-7fb80780194f",

    # --- Past Due 0-30 ---
    "wallingford-pastdue0-30":  "cdc2306a-9f8c-4da0-85fd-62d890740137",
    "torrington-pastdue0-30":   "90f8c7c3-5a48-4499-a2f5-1e1b7383f592",
    "ridgefield-pastdue0-30":   "",
    "newtown-pastdue0-30":      "",
    "newmilford-pastdue0-30":   "",
    "middletown-pastdue0-30":   "",
    "brookfield-pastdue0-30":   "",
}

def forward_to_replify(campaign_id, data, gym_name):
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
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": REPLIFY_API_KEY
    }

    url = BASE_URL.format(campaign_id=campaign_id)
    response = requests.post(url, json=payload, headers=headers)
    logging.info(f"[{gym_name}] Replify response: {response.status_code} - {response.text}")
    return response

@app.route("/webhook/<path:gym_name>", methods=["POST"])
def webhook(gym_name):
    gym_key = gym_name.lower().replace(" ", "")

    if gym_key not in GYMS:
        logging.warning(f"Unknown gym: {gym_name}")
        return jsonify({"error": f"Unknown gym: {gym_name}"}), 404

    if not GYMS[gym_key]:
        logging.warning(f"No campaign ID set for: {gym_name}")
        return jsonify({"error": f"No campaign ID configured for: {gym_name}"}), 400

    data = request.json or request.form.to_dict()
    logging.info(f"[{gym_name}] Received from GleanTap: {data}")

    campaign_id = GYMS[gym_key]
    response = forward_to_replify(campaign_id, data, gym_name)

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
