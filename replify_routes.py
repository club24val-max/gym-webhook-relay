"""
FastAPI routes for Replify webhook listener and analytics queries.
Add these routes to your existing gym-webhook-relay FastAPI app.
"""

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, timedelta
import logging

from replify_call_outcomes import call_analytics, EASTERN

logger = logging.getLogger(__name__)

# Create router to include in main FastAPI app
router = APIRouter(prefix="/api/replify", tags=["replify"])


# ============================================================================
# WEBHOOK ENDPOINTS - Receive call outcomes from Replify
# ============================================================================

@router.post("/webhook/call-outcome")
async def replify_call_outcome_webhook(request: Request):
    """
    Webhook endpoint to receive call outcomes from Replify.
    
    Replify should POST to: https://your-domain.com/api/replify/webhook/call-outcome
    
    Expected payload (adjust based on actual Replify webhook format):
    {
        "call_id": "replify-call-123",
        "phone": "+12035551234",
        "campaign_id": "week_trial",
        "outcome": "answered",  // or "voicemail", "no_answer"
        "duration": 45,
        "disposition": "ANSWERED",
        "club_id": "09556"
    }
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    
    # Extract fields (adjust keys based on actual Replify webhook format)
    phone = payload.get("phone")
    campaign = payload.get("campaign_id")
    outcome = payload.get("outcome", "").lower()
    club_id = payload.get("club_id")
    call_id = payload.get("call_id")
    duration = payload.get("duration", 0)
    disposition = payload.get("disposition")
    
    # Validate required fields
    if not all([phone, campaign, outcome, club_id]):
        logger.warning(f"Missing required fields in webhook: {payload}")
        return JSONResponse(
            {"error": "Missing required fields: phone, campaign_id, outcome, club_id"},
            status_code=400
        )
    
    # Normalize phone (remove formatting)
    phone = ''.join(c for c in phone if c.isdigit())
    if len(phone) < 10:
        return JSONResponse({"error": "Invalid phone number"}, status_code=400)
    
    # Validate outcome
    if outcome not in ["answered", "voicemail", "no_answer"]:
        logger.warning(f"Invalid outcome '{outcome}' in webhook")
        return JSONResponse(
            {"error": f"Invalid outcome. Must be: answered, voicemail, or no_answer"},
            status_code=400
        )
    
    try:
        # Log the call outcome
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
        
        return JSONResponse({
            "status": "success",
            "row_id": row_id,
            "message": f"Call outcome logged: {outcome}"
        })
    
    except Exception as e:
        logger.error(f"Error logging call outcome: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


# ============================================================================
# QUERY ENDPOINTS - Get analytics data
# ============================================================================

@router.get("/analytics/contact-pattern")
async def get_contact_pattern(
    phone: str = Query(...),
    campaign: str = Query(...),
    days: int = Query(30, ge=7, le=365)
):
    """
    Get answer/voicemail/no-answer rates for a specific contact.
    
    Example: /api/replify/analytics/contact-pattern?phone=2035551234&campaign=week_trial&days=30
    """
    try:
        pattern = call_analytics.get_contact_pattern(phone, campaign, days=days)
        return {
            "phone": phone,
            "campaign": campaign,
            "days_analyzed": days,
            "pattern": pattern
        }
    except Exception as e:
        logger.error(f"Error getting contact pattern: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/hourly-patterns")
async def get_hourly_patterns(
    campaign: str = Query(...),
    club_id: Optional[str] = Query(None),
    days: int = Query(30, ge=7, le=365)
):
    """
    Get answer rates broken down by hour and day of week.
    
    Example: /api/replify/analytics/hourly-patterns?campaign=past_due_0_30&club_id=09556&days=30
    
    Returns:
    {
        "campaign": "past_due_0_30",
        "club_id": "09556",
        "by_hour": {0: 0.32, 1: 0.28, ..., 23: 0.45},
        "by_day": {0: 0.42, 1: 0.41, ..., 6: 0.35},
        "heatmap": [[...], [...], ...],  // 24 hours x 7 days
        "peak_hours": [10, 11, 14, 15],
        "worst_hours": [0, 1, 2, 6, 7, 22, 23]
    }
    """
    try:
        patterns = call_analytics.get_hourly_patterns(campaign, club_id=club_id, days=days)
        
        # Identify peak and worst hours
        by_hour = patterns["by_hour"]
        sorted_hours = sorted(by_hour.items(), key=lambda x: x[1], reverse=True)
        peak_hours = [h for h, _ in sorted_hours[:4]]
        worst_hours = [h for h, _ in sorted_hours[-4:]]
        
        return {
            "campaign": campaign,
            "club_id": club_id,
            "days_analyzed": days,
            "by_hour": patterns["by_hour"],
            "by_day": patterns["by_day"],
            "heatmap": patterns["heatmap"],
            "peak_hours": sorted(peak_hours),
            "worst_hours": sorted(worst_hours),
            "analysis": {
                "best_time": f"{peak_hours[0]:02d}:00-{peak_hours[0]+1:02d}:00",
                "avoid_times": [f"{h:02d}:00-{h+1:02d}:00" for h in worst_hours]
            }
        }
    except Exception as e:
        logger.error(f"Error getting hourly patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/retry-recommendation")
async def get_retry_recommendation(
    phone: str = Query(...),
    campaign: str = Query(...)
):
    """
    Get retry recommendation for a contact.
    
    Example: /api/replify/analytics/retry-recommendation?phone=2035551234&campaign=past_due_0_30
    """
    try:
        recommendation = call_analytics.get_retry_recommendation(phone, campaign)
        return {
            "phone": phone,
            "campaign": campaign,
            "recommendation": recommendation
        }
    except Exception as e:
        logger.error(f"Error getting retry recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/summary")
async def get_summary(
    club_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365)
):
    """
    Get overall summary stats across all campaigns.
    Useful for dashboards and quick overview.
    
    Example: /api/replify/analytics/summary?club_id=09556&days=30
    """
    try:
        import sqlite3
        conn = sqlite3.connect(call_analytics.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now(EASTERN) - timedelta(days=days)
        
        # Build query
        base_query = """
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
        
        params = [cutoff.isoformat()]
        
        if club_id:
            base_query += " AND club_id = ?"
            params.append(club_id)
        
        cursor.execute(base_query, params)
        row = cursor.fetchone()
        
        if not row or row[0] == 0:
            conn.close()
            return {
                "club_id": club_id,
                "days": days,
                "total_calls": 0,
                "answer_rate": 0.0,
                "unique_contacts": 0,
                "unique_campaigns": 0
            }
        
        total, answered, vmail, no_ans, contacts, campaigns, avg_dur = row
        answer_rate = (answered / total * 100) if total > 0 else 0
        
        conn.close()
        
        return {
            "club_id": club_id,
            "days": days,
            "total_calls": total,
            "answered_calls": answered,
            "voicemail_calls": vmail,
            "no_answer_calls": no_ans,
            "answer_rate_percent": round(answer_rate, 1),
            "unique_contacts": contacts,
            "unique_campaigns": campaigns,
            "avg_call_duration_seconds": round(avg_dur or 0, 1)
        }
    
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def include_replify_routes(app):
    """
    Add these routes to your existing FastAPI app.
    
    Usage in your main app:
    
    from fastapi import FastAPI
    from replify_routes import include_replify_routes
    
    app = FastAPI()
    include_replify_routes(app)
    """
    app.include_router(router)
