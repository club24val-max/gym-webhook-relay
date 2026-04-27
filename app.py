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
    "ridgefield-pastdue0-30":   "3cbfe5e4-8521-447c-a7e3-795b10aa8467",
    "newtown-pastdue0-30":      "2684b8ea-3c87-413e-89cd-83fc22405287",
    "newmilford-pastdue0-30":   "0681a240-4771-43ba-b0ea-539e9dc760ab",
    "middletown-pastdue0-30":   "97391e22-f568-473f-a234-3f4c978f0e25",
    "brookfield-pastdue0-30":   "3fddf132-90fb-4b1c-b287-19d6468478bb",

    # --- Past Due 31-60 ---
    "wallingford-pastdue31-60": "bead3dd7-4bad-4a8d-8862-7a057acf069a",
    "torrington-pastdue31-60":  "a85aa596-0c39-4d45-b119-a9ce09a26460",
    "ridgefield-pastdue31-60":  "8b581d95-4287-4cfc-a4cf-7e533c24dc22",
    "newtown-pastdue31-60":     "94d1f0ee-c4fb-4887-8dc7-b69df1c99157",
    "newmilford-pastdue31-60":  "08ce2214-369c-4a12-8416-56a46e32200d",
    "middletown-pastdue31-60":  "447b3a5a-0dfd-42ff-a5b4-164ab820e0d5",
    "brookfield-pastdue31-60":  "63aa4d47-7428-48f9-bff2-8124b16686fc",

    # --- Past Due 61-90 ---
    "wallingford-pastdue61-90": "128f0096-de10-43a5-82d0-f92f668bacd0",
    "torrington-pastdue61-90":  "216579c4-de5d-49dd-b105-83293b3c3e18",
    "ridgefield-pastdue61-90":  "4f968f09-a704-4245-9223-653804e14e9c",
    "newtown-pastdue61-90":     "e662751d-a7e7-4cdf-a60b-bb6ef92aaad3",
    "newmilford-pastdue61-90":  "7b019ef7-de80-4746-b39a-ff20defc57b7",
    "middletown-pastdue61-90":  "fadc497d-5375-434e-8c4d-a2c037ada327",
    "brookfield-pastdue61-90":  "6a5dfefc-94cd-42ca-9b82-5bdfb8bc52d1",

    # --- PT Past Due 0-30 ---
    "wallingford-ptpastdue0-30":  "40b4abcd-f2fc-4487-9d28-3e98bc6acfd2",
    "torrington-ptpastdue0-30":   "c8820391-9be2-40ee-bb12-7fe974a0d89d",
    "ridgefield-ptpastdue0-30":   "10a65701-cc63-4bc3-bfd8-6f335c5ee531",
    "newtown-ptpastdue0-30":      "2b03f651-88ed-4ed1-9cba-344743da47a7",
    "newmilford-ptpastdue0-30":   "6c2e6259-1d19-4c98-98bc-01ecaac8901c",
    "middletown-ptpastdue0-30":   "538923b0-acaa-41d7-8cd2-86fde68e6769",
    "brookfield-ptpastdue0-30":   "55565835-d297-4c5b-b4f5-d9ca51245fa9",

    # --- PT Past Due 31-60 ---
    "wallingford-ptpastdue31-60": "6b5200f0-cf2a-4353-868e-2083e1fc3955",
    "torrington-ptpastdue31-60":  "2c9c3fc2-e575-4a1c-b788-4af5a87aa656",
    "ridgefield-ptpastdue31-60":  "337f4b83-1836-49db-9b0f-dee5fbd78c01",
    "newtown-ptpastdue31-60":     "5fbf5606-15a8-40a0-924e-da21234f9481",
    "newmilford-ptpastdue31-60":  "06a91e4c-2ed2-48ac-ad95-c5438b267af9",
    "middletown-ptpastdue31-60":  "efbd172e-0087-4ea9-9e78-09f3b8b0682d",
    "brookfield-ptpastdue31-60":  "367cc250-e51c-4c6a-ab50-11a5bfe64977",

    # --- PT Past Due 61-90 ---
    "wallingford-ptpastdue61-90": "7b4264e6-e409-4210-9708-b3e7dc27d485",
    "torrington-ptpastdue61-90":  "9b6a1dc2-570a-45c0-8cc9-8e3dbe4cf9b7",
    "ridgefield-ptpastdue61-90":  "b5b6abae-95e8-4cf6-97b4-9defc2840274",
    "newtown-ptpastdue61-90":     "25f4113f-8854-430b-b737-00edad1b62c2",
    "newmilford-ptpastdue61-90":  "be4ead7c-6a1a-4ca3-a9a1-6043bcb7d0f6",
    "middletown-ptpastdue61-90":  "745714c3-76d2-4cf5-806d-8661d95f4a49",
    "brookfield-ptpastdue61-90":  "02ac7b55-4430-4062-91d1-b43d6bd8c3ef",

    # --- Cancelled Member Month 1 ---
    "wallingford-cancelled-month1":  "8da653cb-d4ca-4fbf-a24d-8ef5b765647e",
    "torrington-cancelled-month1":   "",
    "ridgefield-cancelled-month1":   "",
    "newtown-cancelled-month1":      "",
    "newmilford-cancelled-month1":   "",
    "middletown-cancelled-month1":   "",
    "brookfield-cancelled-month1":   "",

    # --- Cancelled Member Month 2 ---
    "wallingford-cancelled-month2":  "56e7f372-f7a5-4881-a89d-e55566202e3f",
    "torrington-cancelled-month2":   "",
    "ridgefield-cancelled-month2":   "",
    "newtown-cancelled-month2":      "",
    "newmilford-cancelled-month2":   "",
    "middletown-cancelled-month2":   "",
    "brookfield-cancelled-month2":   "",

    # --- Cancelled Member Month 3 ---
    "wallingford-cancelled-month3":  "bfead2ac-15fe-4b8c-b189-bca4eec5e2a4",
    "torrington-cancelled-month3":   "",
    "ridgefield-cancelled-month3":   "",
    "newtown-cancelled-month3":      "",
    "newmilford-cancelled-month3":   "",
    "middletown-cancelled-month3":   "",
    "brookfield-cancelled-month3":   "",
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
