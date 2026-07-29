from typing import List, Dict, Any, Optional
from app.graph.client import MSGraphClient

class TodoService:
    @staticmethod
    def get_todos(access_token: Optional[str] = None) -> List[Dict[str, Any]]:
        if access_token:
            client = MSGraphClient(access_token)
            res = client.get("me/todo/lists")
            if res and "value" in res and len(res["value"]) > 0:
                list_id = res["value"][0]["id"]
                tasks_res = client.get(f"me/todo/lists/{list_id}/tasks")
                if tasks_res and "value" in tasks_res:
                    tasks = []
                    for idx, task in enumerate(tasks_res["value"]):
                        tasks.append({
                            "id": idx + 1,
                            "text": task.get("title", "Task"),
                            "done": task.get("status") == "completed",
                            "priority": "high" if idx < 2 else "medium"
                        })
                    return tasks

        # Fallback structured MS To-Do items
        return [
            {"id": 1, "text": "Literature Review – Chapter 2", "done": True, "priority": "low"},
            {"id": 2, "text": "Fix bibliography citations", "done": False, "priority": "high"},
            {"id": 3, "text": "Write FYP Chapter 3 introduction", "done": False, "priority": "high"},
            {"id": 4, "text": "Email Prof. Williams (Drafts)", "done": True, "priority": "medium"},
            {"id": 5, "text": "Submit conference abstract", "done": False, "priority": "medium"}
        ]
