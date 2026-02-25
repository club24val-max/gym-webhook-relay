from flask import Flask, request, jsonify
import requests
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

REPLIFY_API_KEY = "KZ3RAX9xJmzmLZJGMcOt4zDx94rHQd89fnlLTFEj"
BASE_URL = "https://api.heylibby.com/api/v1/campaigns/{campaign_id}/contacts"

GYMS = {
    "wallingford":  "51fa892f-11c5-4464-a1b8-747be89139fa",
    "torrington":   "87396182-4f0d-4d8d-b996-dfebbf355a3b",
    "ridgefield":   "8c5612c3-dce9-4e72-b926-eee2b178006e",
    "newtown":      "16e2cb63-1b40-484b-9d1c-561e2c659a35",
    "newmilford":   "b819041d-9ac8-41cc-835a-9ecdc4ba9cde",
    "middletown":   "526b3220-5831-4da7-b56c-38de83037af5",
    "brookfield":   "f5c30a3e-1bb3-4ed4-83b9-7fb80780194f",
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
                    "source": "week_trial_form",
                    "gym": gym_name
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

@app.route("/webhook/<gym_name>", methods=["POST"])
def webhook(gym_name):
    gym_key = gym_name.lower().replace("-", "").replace(" ", "")

    if gym_key not in GYMS:
        logging.warning(f"Unknown gym: {gym_name}")
        return jsonify({"error": f"Unknown gym: {gym_name}"}), 404

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
