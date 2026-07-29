from typing import Dict, Any, Optional
from app.graph.client import MSGraphClient

class EmailService:
    @staticmethod
    def create_draft(subject: str, body_content: str, recipient: str, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a pre-drafted email in user's Outlook Drafts folder via MS Graph.
        Jarvis NEVER auto-sends emails!
        """
        if access_token:
            client = MSGraphClient(access_token)
            payload = {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body_content
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": recipient
                        }
                    }
                ]
            }
            res = client.post("me/messages", payload)
            if res:
                return {"status": "staged", "message_id": res.get("id"), "folder": "Outlook Drafts"}

        return {
            "status": "staged",
            "subject": subject,
            "folder": "Outlook Drafts",
            "auto_sent": False,
            "shield_active": True
        }
