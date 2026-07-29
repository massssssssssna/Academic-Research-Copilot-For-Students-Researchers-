from typing import List, Dict, Any, Optional
from app.graph.client import MSGraphClient

class CalendarService:
    @staticmethod
    def get_events(access_token: Optional[str] = None) -> List[Dict[str, Any]]:
        if access_token:
            client = MSGraphClient(access_token)
            res = client.get("me/events?$top=10&$select=subject,start,end")
            if res and "value" in res:
                events = []
                for idx, ev in enumerate(res["value"]):
                    events.append({
                        "id": idx + 1,
                        "title": ev.get("subject", "Academic Block"),
                        "day": "Upcoming",
                        "clock": ev.get("start", {}).get("dateTime", "")[:16].replace("T", " "),
                        "color": "indigo" if idx % 2 == 0 else "teal",
                        "icon": "📚",
                        "isNew": idx == 0
                    })
                return events

        # Fallback structured calendar events
        return [
            {"id": 1, "title": "Deep Work: FYP Chapter 3", "day": "Tomorrow", "clock": "4:00 – 7:00 PM", "color": "indigo", "icon": "📚", "isNew": True},
            {"id": 2, "title": "Supervisor Meeting", "day": "Thursday", "clock": "10:00 AM", "color": "teal", "icon": "👨‍🏫", "isNew": False},
            {"id": 3, "title": "Literature Review Session", "day": "Friday", "clock": "2:00 – 4:00 PM", "color": "indigo", "icon": "📖", "isNew": False}
        ]
