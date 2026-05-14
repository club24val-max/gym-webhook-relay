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


# ============================================================================
# DATA VIEWER - See your data in a browser
# ============================================================================

@replify_bp.route("/data", methods=["GET"])
def view_data():
    """
    Browse your call data in a browser.
    Visit: https://gym-webhook-relay.onrender.com/api/replify/data
    """
    import sqlite3
    days = int(request.args.get("days", 30))
    club_id = request.args.get("club_id")

    conn = sqlite3.connect(call_analytics.db_path)
    cursor = conn.cursor()
    cutoff = (datetime.now(EASTERN) - timedelta(days=days)).isoformat()

    # Summary stats
    q = "SELECT COUNT(*), SUM(CASE WHEN outcome='answered' THEN 1 ELSE 0 END), SUM(CASE WHEN outcome='voicemail' THEN 1 ELSE 0 END), SUM(CASE WHEN outcome='no_answer' THEN 1 ELSE 0 END) FROM call_history WHERE timestamp > ?"
    params = [cutoff]
    if club_id:
        q += " AND club_id = ?"
        params.append(club_id)
    cursor.execute(q, params)
    total, answered, vmail, no_ans = cursor.fetchone()
    total = total or 0
    answered = answered or 0
    vmail = vmail or 0
    no_ans = no_ans or 0
    rate = round((answered / total * 100), 1) if total > 0 else 0

    # Recent calls
    q2 = "SELECT phone, campaign, outcome, club_id, duration_seconds, timestamp FROM call_history WHERE timestamp > ?"
    params2 = [cutoff]
    if club_id:
        q2 += " AND club_id = ?"
        params2.append(club_id)
    q2 += " ORDER BY timestamp DESC LIMIT 100"
    cursor.execute(q2, params2)
    rows = cursor.fetchall()
    conn.close()

    rows_html = ""
    for phone, campaign, outcome, cid, dur, ts in rows:
        color = "#2d8659" if outcome == "answered" else "#c9a227" if outcome == "voicemail" else "#c45c3a"
        rows_html += f'<tr><td>{ts[:19]}</td><td>{phone}</td><td>{campaign}</td><td style="color:{color};font-weight:600">{outcome}</td><td>{cid}</td><td>{dur or 0}s</td></tr>'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Replify Analytics - Club 24</title>
<style>
  body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 20px; background: #f5f5f0; color: #2c2c2a; }}
  h1 {{ font-size: 24px; margin: 0 0 8px; }}
  .sub {{ color: #888; font-size: 14px; margin-bottom: 24px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .stat {{ background: #fff; border-radius: 10px; padding: 16px; border: 1px solid #ddd; }}
  .stat-label {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }}
  .stat-value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; border: 1px solid #ddd; }}
  th {{ background: #2c2c2a; color: #fff; padding: 10px 12px; text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
  td {{ padding: 10px 12px; border-top: 1px solid #eee; font-size: 14px; }}
  tr:hover {{ background: #f9f9f5; }}
  .filters {{ margin-bottom: 16px; font-size: 14px; }}
  .filters a {{ margin-right: 12px; color: #1d9e75; text-decoration: none; }}
  .filters a:hover {{ text-decoration: underline; }}
  .green {{ color: #1d9e75; }}
</style></head><body>
<h1>Replify Call Analytics</h1>
<p class="sub">Last {days} days{f' &mdash; Club {club_id}' if club_id else ' &mdash; All clubs'}</p>
<div class="filters">
  Filter by club:
  <a href="?days={days}">All</a>
  <a href="?days={days}&club_id=09556">Wallingford</a>
  <a href="?days={days}&club_id=09557">Torrington</a>
  <a href="?days={days}&club_id=09558">Ridgefield</a>
  <a href="?days={days}&club_id=09559">Newtown</a>
  <a href="?days={days}&club_id=09560">New Milford</a>
  <a href="?days={days}&club_id=09561">Middletown</a>
  <a href="?days={days}&club_id=09562">Brookfield</a>
  &nbsp;|&nbsp; Days:
  <a href="?days=7{'&club_id=' + club_id if club_id else ''}">7d</a>
  <a href="?days=14{'&club_id=' + club_id if club_id else ''}">14d</a>
  <a href="?days=30{'&club_id=' + club_id if club_id else ''}">30d</a>
  <a href="?days=60{'&club_id=' + club_id if club_id else ''}">60d</a>
  <a href="?days=90{'&club_id=' + club_id if club_id else ''}">90d</a>
</div>
<div class="stats">
  <div class="stat"><div class="stat-label">Total calls</div><div class="stat-value">{total}</div></div>
  <div class="stat"><div class="stat-label">Answer rate</div><div class="stat-value green">{rate}%</div></div>
  <div class="stat"><div class="stat-label">Answered</div><div class="stat-value">{answered}</div></div>
  <div class="stat"><div class="stat-label">Voicemail</div><div class="stat-value">{vmail}</div></div>
  <div class="stat"><div class="stat-label">No answer</div><div class="stat-value">{no_ans}</div></div>
</div>
<table>
  <thead><tr><th>Time</th><th>Phone</th><th>Campaign</th><th>Outcome</th><th>Club</th><th>Duration</th></tr></thead>
  <tbody>{rows_html if rows_html else '<tr><td colspan="6" style="text-align:center;padding:40px;color:#888">No calls logged yet. Send a test or configure Replify webhooks.</td></tr>'}</tbody>
</table>
</body></html>"""

    return html, 200, {"Content-Type": "text/html"}
