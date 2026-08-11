from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from app.graph.client import MSGraphClient

class CalendarService:
    @staticmethod
    def get_events(access_token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch upcoming calendar events from today (PKT) forward. Never returns past events."""
        if access_token:
            try:
                client = MSGraphClient(access_token)
                # PKT = UTC+5, use it for correct "today"
                pkt = timezone(timedelta(hours=5))
                now_pkt = datetime.now(pkt)
                today_str = now_pkt.strftime("%Y-%m-%d")

                # Date-filtered calendarView — never shows past events
                start_dt = now_pkt.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                end_dt = (now_pkt + timedelta(days=30)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                res = client.get(
                    f"me/calendarView?startDateTime={start_dt}&endDateTime={end_dt}"
                    "&$top=10&$select=subject,start,end&$orderby=start/dateTime asc"
                )
                if res and "value" in res:
                    events = []
                    for idx, ev in enumerate(res["value"]):
                        s_raw = ev.get("start", {}).get("dateTime", "")
                        s_date = s_raw[:10] if s_raw else ""
                        s_time = s_raw[11:16] if len(s_raw) > 11 else ""

                        if s_date == today_str:
                            day_label = "Today"
                        elif s_date == (now_pkt + timedelta(days=1)).strftime("%Y-%m-%d"):
                            day_label = "Tomorrow"
                        elif s_date:
                            # e.g. "Aug 15"
                            try:
                                dt = datetime.strptime(s_date, "%Y-%m-%d")
                                day_label = dt.strftime("%b %d")
                            except Exception:
                                day_label = s_date
                        else:
                            day_label = "Upcoming"

                        events.append({
                            "id": idx + 1,
                            "title": ev.get("subject", "Untitled Event"),
                            "day": day_label,
                            "clock": s_time or "—",
                            "color": "indigo" if idx % 2 == 0 else "teal",
                            "icon": "📅",
                            "isNew": idx == 0,
                        })
                    if events:
                        return events
            except Exception as e:
                print(f"[CalendarService] Error fetching events: {e}")

        # Fallback: generic academic schedule (no fake dates)
        return [
            {"id": 1, "title": "Deep Work: FYP Chapter 3", "day": "Today", "clock": "4:00 PM", "color": "indigo", "icon": "📚", "isNew": True},
            {"id": 2, "title": "Supervisor Meeting", "day": "Thursday", "clock": "10:00 AM", "color": "teal", "icon": "👨‍🏫", "isNew": False},
            {"id": 3, "title": "Literature Review Session", "day": "Friday", "clock": "2:00 PM", "color": "indigo", "icon": "📖", "isNew": False},
        ]
