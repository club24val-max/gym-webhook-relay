"""
Replify Call Outcomes Webhook Listener & Logger
Captures call results (answered, voicemail, no-answer) from Replify API callbacks.
Integrates with gym-webhook-relay FastAPI app.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
import pytz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DB_PATH = Path(__file__).parent / "call_analytics.db"

# Eastern timezone for all timestamp operations
EASTERN = pytz.timezone('America/New_York')


class CallAnalytics:
    """Handle all call logging and outcome tracking."""
    
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main call history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                campaign TEXT NOT NULL,
                outcome TEXT NOT NULL,
                hour_of_day INTEGER,
                day_of_week INTEGER,
                timestamp DATETIME NOT NULL,
                club_id TEXT,
                replify_call_id TEXT UNIQUE,
                duration_seconds INTEGER,
                disposition TEXT,
                notes TEXT
            );
        """)
        
        # Call retry tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_retries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                campaign TEXT NOT NULL,
                original_call_id TEXT,
                attempt_number INTEGER,
                last_outcome TEXT,
                next_retry_window TEXT,
                scheduled_retry_time DATETIME,
                created_at DATETIME,
                updated_at DATETIME
            );
        """)
        
        # Hourly statistics cache (for dashboard performance)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hourly_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign TEXT NOT NULL,
                club_id TEXT,
                hour_of_day INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                total_calls INTEGER DEFAULT 0,
                answered_count INTEGER DEFAULT 0,
                voicemail_count INTEGER DEFAULT 0,
                no_answer_count INTEGER DEFAULT 0,
                answer_rate REAL DEFAULT 0.0,
                date_recorded DATE NOT NULL,
                UNIQUE(campaign, club_id, hour_of_day, day_of_week, date_recorded)
            );
        """)
        
        # Create indices for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_call_history_phone_campaign 
            ON call_history(phone, campaign)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_call_history_timestamp 
            ON call_history(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_call_history_hour_day 
            ON call_history(hour_of_day, day_of_week)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hourly_stats_campaign 
            ON hourly_stats(campaign, date_recorded)
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def log_call_outcome(
        self,
        phone: str,
        campaign: str,
        outcome: str,
        club_id: str,
        replify_call_id: Optional[str] = None,
        duration_seconds: int = 0,
        disposition: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """
        Log a call outcome to the database.
        
        Args:
            phone: Contact phone number
            campaign: Campaign type (week_trial, past_due_0_30, etc.)
            outcome: 'answered', 'voicemail', or 'no_answer'
            club_id: Club location ID
            replify_call_id: Replify's call ID
            duration_seconds: Call duration
            disposition: Raw Replify disposition if available
            notes: Optional notes
        
        Returns:
            Database row ID
        """
        if outcome not in ["answered", "voicemail", "no_answer"]:
            raise ValueError(f"Invalid outcome: {outcome}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now(EASTERN)
        
        cursor.execute("""
            INSERT INTO call_history
            (phone, campaign, outcome, hour_of_day, day_of_week, timestamp, 
             club_id, replify_call_id, duration_seconds, disposition, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            phone,
            campaign,
            outcome,
            now.hour,
            now.weekday(),
            now.isoformat(),
            club_id,
            replify_call_id,
            duration_seconds,
            disposition,
            notes
        ))
        
        row_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Logged {outcome} for {phone} (campaign: {campaign}, club: {club_id})")
        
        # Update hourly stats cache
        self._update_hourly_stats(campaign, club_id, now.hour, now.weekday(), outcome)
        
        return row_id
    
    def _update_hourly_stats(self, campaign: str, club_id: str, hour: int, day_of_week: int, outcome: str):
        """Update hourly statistics cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now(EASTERN).date()
        
        # Check if record exists
        cursor.execute("""
            SELECT id, total_calls, answered_count, voicemail_count, no_answer_count
            FROM hourly_stats
            WHERE campaign = ? AND club_id = ? AND hour_of_day = ? 
              AND day_of_week = ? AND date_recorded = ?
        """, (campaign, club_id, hour, day_of_week, today))
        
        row = cursor.fetchone()
        
        if row:
            # Update existing
            stat_id, total, answered, vmail, no_ans = row
            
            if outcome == "answered":
                answered += 1
            elif outcome == "voicemail":
                vmail += 1
            elif outcome == "no_answer":
                no_ans += 1
            
            total += 1
            answer_rate = (answered / total * 100) if total > 0 else 0
            
            cursor.execute("""
                UPDATE hourly_stats
                SET total_calls = ?, answered_count = ?, voicemail_count = ?, 
                    no_answer_count = ?, answer_rate = ?
                WHERE id = ?
            """, (total, answered, vmail, no_ans, answer_rate, stat_id))
        else:
            # Insert new
            answered = 1 if outcome == "answered" else 0
            vmail = 1 if outcome == "voicemail" else 0
            no_ans = 1 if outcome == "no_answer" else 0
            answer_rate = 100 if outcome == "answered" else 0
            
            cursor.execute("""
                INSERT INTO hourly_stats
                (campaign, club_id, hour_of_day, day_of_week, total_calls, 
                 answered_count, voicemail_count, no_answer_count, answer_rate, date_recorded)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (campaign, club_id, hour, day_of_week, 1, answered, vmail, no_ans, answer_rate, today))
        
        conn.commit()
        conn.close()
    
    def get_contact_pattern(self, phone: str, campaign: str, days: int = 30) -> dict:
        """
        Get answer/voicemail/no-answer rates for a contact over the past N days.
        
        Returns:
            {
                'answered': 0.5,
                'voicemail': 0.3,
                'no_answer': 0.2,
                'total_attempts': 10,
                'last_outcome': 'answered'
            }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now(EASTERN) - timedelta(days=days)
        
        # Get outcome distribution
        cursor.execute("""
            SELECT outcome, COUNT(*) as count
            FROM call_history
            WHERE phone = ? AND campaign = ? AND timestamp > ?
            GROUP BY outcome
        """, (phone, campaign, cutoff.isoformat()))
        
        stats = cursor.fetchall()
        total = sum(count for _, count in stats)
        
        if total == 0:
            return {
                "answered": 0.0,
                "voicemail": 0.0,
                "no_answer": 1.0,
                "total_attempts": 0,
                "last_outcome": None
            }
        
        pattern = {outcome: count / total for outcome, count in stats}
        
        # Get last outcome
        cursor.execute("""
            SELECT outcome FROM call_history
            WHERE phone = ? AND campaign = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (phone, campaign))
        
        last = cursor.fetchone()
        pattern["last_outcome"] = last[0] if last else None
        pattern["total_attempts"] = total
        
        conn.close()
        return pattern
    
    def get_hourly_patterns(self, campaign: str, club_id: Optional[str] = None, days: int = 30) -> dict:
        """
        Get answer rates broken down by hour of day and day of week.
        
        Returns:
            {
                'by_hour': {0: 0.45, 1: 0.32, ..., 23: 0.28},
                'by_day': {0: 0.52, 1: 0.49, ..., 6: 0.41},
                'heatmap': [[hour0_mon, hour0_tue, ...], [...], ...]
            }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now(EASTERN) - timedelta(days=days)
        
        # Hour patterns
        query = """
            SELECT hour_of_day, answer_rate, total_calls
            FROM hourly_stats
            WHERE campaign = ? AND timestamp > ?
        """
        params = [campaign, cutoff.isoformat()]
        
        if club_id:
            query += " AND club_id = ?"
            params.append(club_id)
        
        cursor.execute(query, params)
        hour_data = cursor.fetchall()
        
        # Aggregate by hour across all dates
        by_hour = {}
        for hour in range(24):
            hour_stats = [h for h in hour_data if h[0] == hour]
            if hour_stats:
                total_calls = sum(h[2] for h in hour_stats)
                avg_rate = sum(h[1] * h[2] for h in hour_stats) / total_calls
                by_hour[hour] = round(avg_rate / 100, 2)  # Convert percentage to decimal
            else:
                by_hour[hour] = 0.0
        
        # Day patterns
        cursor.execute("""
            SELECT day_of_week, answer_rate, total_calls
            FROM hourly_stats
            WHERE campaign = ? AND timestamp > ?
        """ + (" AND club_id = ?" if club_id else ""), 
        (campaign, cutoff.isoformat()) + ((club_id,) if club_id else ()))
        
        day_data = cursor.fetchall()
        by_day = {}
        for day in range(7):
            day_stats = [d for d in day_data if d[0] == day]
            if day_stats:
                total_calls = sum(d[2] for d in day_stats)
                avg_rate = sum(d[1] * d[2] for d in day_stats) / total_calls
                by_day[day] = round(avg_rate / 100, 2)
            else:
                by_day[day] = 0.0
        
        # Build heatmap: 7 days × 24 hours
        heatmap = []
        for hour in range(24):
            hour_row = []
            for day in range(7):
                cursor.execute("""
                    SELECT answer_rate FROM hourly_stats
                    WHERE campaign = ? AND hour_of_day = ? AND day_of_week = ?
                    AND timestamp > ?
                """ + (" AND club_id = ?" if club_id else ""),
                (campaign, hour, day, cutoff.isoformat()) + ((club_id,) if club_id else ()))
                
                result = cursor.fetchone()
                rate = (result[0] / 100) if result else 0.0
                hour_row.append(round(rate, 2))
            heatmap.append(hour_row)
        
        conn.close()
        
        return {
            "by_hour": by_hour,
            "by_day": by_day,
            "heatmap": heatmap
        }
    
    def get_retry_recommendation(self, phone: str, campaign: str) -> dict:
        """
        Determine if a contact should be retried and when.
        
        Returns:
            {
                'should_retry': True,
                'reason': 'voicemail_left - wait 2 hours',
                'optimal_window': '10:00-11:00',
                'next_retry_after': '2024-01-15 15:30:00'
            }
        """
        pattern = self.get_contact_pattern(phone, campaign)
        
        if pattern["total_attempts"] == 0:
            return {
                "should_retry": True,
                "reason": "first_attempt",
                "optimal_window": None,
                "next_retry_after": None
            }
        
        last_outcome = pattern["last_outcome"]
        now = datetime.now(EASTERN)
        
        # Calculate retry recommendation based on last outcome
        if last_outcome == "answered":
            return {
                "should_retry": False,
                "reason": "answered - no retry needed",
                "optimal_window": None,
                "next_retry_after": None
            }
        
        if last_outcome == "voicemail":
            # Wait 2 hours before retry
            next_retry = now + timedelta(hours=2)
            return {
                "should_retry": True,
                "reason": "voicemail_left - wait 2 hours for message review",
                "optimal_window": None,
                "next_retry_after": next_retry.isoformat()
            }
        
        if last_outcome == "no_answer":
            # Only retry during peak hours
            attempt_count = pattern["total_attempts"]
            if attempt_count >= 3:
                return {
                    "should_retry": False,
                    "reason": "max_retries_reached",
                    "optimal_window": None,
                    "next_retry_after": None
                }
            
            # Suggest next optimal window (same day if it's morning, next day if evening)
            current_hour = now.hour
            if current_hour < 10:
                # Morning - suggest 2–3pm same day
                next_retry = now.replace(hour=14, minute=0, second=0)
            elif current_hour < 16:
                # Afternoon - suggest 10am next day
                next_retry = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0)
            else:
                # Evening - suggest 10am next day
                next_retry = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0)
            
            return {
                "should_retry": True,
                "reason": f"no_answer (attempt {attempt_count}/3) - retry during peak hours",
                "optimal_window": f"{next_retry.hour:02d}:00-{next_retry.hour+1:02d}:00",
                "next_retry_after": next_retry.isoformat()
            }
        
        return {
            "should_retry": False,
            "reason": "unknown",
            "optimal_window": None,
            "next_retry_after": None
        }


# Export for use in FastAPI app
call_analytics = CallAnalytics()
