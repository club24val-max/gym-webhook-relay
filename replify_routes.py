"""
Replify Call Outcomes - Flask Routes
Receives call outcomes from Replify webhooks and exposes analytics APIs.
"""

from flask import Blueprint, request, jsonify
import logging

from replify_call_outcomes import call_analytics, EASTERN
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

replify_bp = Blueprint('replify', __name__, url_prefix='/api/replify')


# ============================================================================
# WEBHOOK ENDPOINT - Receive call outcomes from Replify
# ============================================================================

@replify_bp.route("/webhook/call-outcome", methods=["POST"])
def replify_call_outcome_webhook():
    """
    Webhook endpoint to receive call outcomes from Replify.
    POST to: https://your-domain.com/api/replify/webhook/call-outcome
    """
    try:
        payload = request.json or request.form.to_dict()
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        return jsonify({"error": "Invalid JSON"}), 400

    phone = payload.get("phone")
    campaign = payload.get("campaign_id")
    outcome = (payload.get("outcome") or "").lower()
    club_id = payload.get("club_id")
    call_id = payload.get("call_id")
    duration = payload.get("duration", 0)
    disposition = payload.get("disposition")

    if not all([phone, campaign, outcome, club_id]):
        logger.warning(f"Missing required fields in webhook: {payload}")
        return jsonify({"error": "Missing required fields: phone, campaign_id, outcome, club_id"}), 400

    phone = ''.join(c for c in phone if c.isdigit())
    if len(phone) < 10:
        return jsonify({"error": "Invalid phone number"}), 400

    if outcome not in ["answered", "voicemail", "no_answer"]:
        logger.warning(f"Invalid outcome '{outcome}' in webhook")
        return jsonify({"error": "Invalid outcome. Must be: answered, voicemail, or no_answer"}), 400

    try:
        row_id = call_analytics.log_call_outcome(
            phone=phone,
            campaign=campaign,
            outcome=outcome,
            club_id=club_id,
            replify_call_id=call_id,
            duration_seconds=duration,
            disposition=disposition
        )
        logger.info(f"Logged call outcome: {phone} / {campaign} / {outcome}")
        return jsonify({"status": "success", "row_id": row_id, "message": f"Call outcome logged: {outcome}"})
    except Exception as e:
        logger.error(f"Error logging call outcome: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# QUERY ENDPOINTS - Analytics
# ============================================================================

@replify_bp.route("/analytics/contact-pattern", methods=["GET"])
def get_contact_pattern():
    phone = request.args.get("phone")
    campaign = request.args.get("campaign")
    days = int(request.args.get("days", 30))

    if not phone or not campaign:
        return jsonify({"error": "Missing phone or campaign parameter"}), 400

    try:
        pattern = call_analytics.get_contact_pattern(phone, campaign, days=days)
        return jsonify({"phone": phone, "campaign": campaign, "days_analyzed": days, "pattern": pattern})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@replify_bp.route("/analytics/hourly-patterns", methods=["GET"])
def get_hourly_patterns():
    campaign = request.args.get("campaign")
    club_id = request.args.get("club_id")
    days = int(request.args.get("days", 30))

    if not campaign:
        return jsonify({"error": "Missing campaign parameter"}), 400

    try:
        patterns = call_analytics.get_hourly_patterns(campaign, club_id=club_id, days=days)
        by_hour = patterns["by_hour"]
        sorted_hours = sorted(by_hour.items(), key=lambda x: x[1], reverse=True)
        peak_hours = [h for h, _ in sorted_hours[:4]]
        worst_hours = [h for h, _ in sorted_hours[-4:]]

        return jsonify({
            "campaign": campaign,
            "club_id": club_id,
            "days_analyzed": days,
            "by_hour": patterns["by_hour"],
            "by_day": patterns["by_day"],
            "heatmap": patterns["heatmap"],
            "peak_hours": sorted(peak_hours),
            "worst_hours": sorted(worst_hours),
            "analysis": {
                "best_time": f"{peak_hours[0]:02d}:00-{peak_hours[0]+1:02d}:00" if peak_hours else "N/A",
                "avoid_times": [f"{h:02d}:00-{h+1:02d}:00" for h in worst_hours]
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@replify_bp.route("/analytics/retry-recommendation", methods=["GET"])
def get_retry_recommendation():
    phone = request.args.get("phone")
    campaign = request.args.get("campaign")

    if not phone or not campaign:
        return jsonify({"error": "Missing phone or campaign parameter"}), 400

    try:
        recommendation = call_analytics.get_retry_recommendation(phone, campaign)
        return jsonify({"phone": phone, "campaign": campaign, "recommendation": recommendation})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@replify_bp.route("/analytics/summary", methods=["GET"])
def get_summary():
    club_id = request.args.get("club_id")
    days = int(request.args.get("days", 30))

    try:
        import sqlite3
        conn = sqlite3.connect(call_analytics.db_path)
        cursor = conn.cursor()
        cutoff = (datetime.now(EASTERN) - timedelta(days=days)).isoformat()

        query = """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN outcome = 'answered' THEN 1 ELSE 0 END) as answered,
                   SUM(CASE WHEN outcome = 'voicemail' THEN 1 ELSE 0 END) as voicemail,
                   SUM(CASE WHEN outcome = 'no_answer' THEN 1 ELSE 0 END) as no_answer,
                   COUNT(DISTINCT phone) as unique_contacts,
                   COUNT(DISTINCT campaign) as unique_campaigns,
                   AVG(duration_seconds) as avg_duration
            FROM call_history
            WHERE timestamp > ?
        """
        params = [cutoff]

        if club_id:
            query += " AND club_id = ?"
            params.append(club_id)

        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()

        if not row or row[0] == 0:
            return jsonify({
                "club_id": club_id, "days": days, "total_calls": 0,
                "answer_rate_percent": 0.0, "unique_contacts": 0, "unique_campaigns": 0
            })

        total, answered, vmail, no_ans, contacts, campaigns, avg_dur = row
        answer_rate = (answered / total * 100) if total > 0 else 0

        return jsonify({
            "club_id": club_id, "days": days, "total_calls": total,
            "answered_calls": answered, "voicemail_calls": vmail, "no_answer_calls": no_ans,
            "answer_rate_percent": round(answer_rate, 1),
            "unique_contacts": contacts, "unique_campaigns": campaigns,
            "avg_call_duration_seconds": round(avg_dur or 0, 1)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
