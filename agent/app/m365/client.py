# app/m365/client.py
import requests
from typing import Any, Dict, Optional
from datetime import datetime, timedelta, timezone

GRAPH = "https://graph.microsoft.com/v1.0"

def _utc_iso(dt: datetime) -> str:
    # Graph likes: 2026-02-17T00:00:00Z
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class M365Client:
    def __init__(self, access_token: str):
        self.h = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def me(self) -> Dict[str, Any]:
        r = requests.get(f"{GRAPH}/me", headers=self.h, timeout=30)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Legacy: simple sendMail (no message id returned by Graph)
    # ------------------------------------------------------------------
    def send_mail(self, to_email: str, subject: str, body_text: str) -> bool:
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body_text},
                "toRecipients": [{"emailAddress": {"address": to_email}}],
            },
            "saveToSentItems": True,
        }
        r = requests.post(f"{GRAPH}/me/sendMail", headers=self.h, json=payload, timeout=30)
        r.raise_for_status()
        return True

    # ------------------------------------------------------------------
    # Production: draft -> send by id (gives you ids for reply tracking)
    # ------------------------------------------------------------------
    def create_draft(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        *,
        reply_to_message_id: Optional[str] = None,
        in_reply_to_internet_message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a draft message and returns the message object including:
          - id
          - conversationId
          - internetMessageId (often present in sent items)
        """
        message: Dict[str, Any] = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body_text},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        }

        # NOTE:
        # - Graph supports creating replies via /messages/{id}/createReply, which is better than guessing headers.
        # - Keeping these optional fields here for future, but the safer path is createReply().
        if in_reply_to_internet_message_id:
            message["internetMessageHeaders"] = [
                {"name": "In-Reply-To", "value": in_reply_to_internet_message_id}
            ]

        payload = message

        r = requests.post(f"{GRAPH}/me/messages", headers=self.h, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def send_draft(self, message_id: str) -> bool:
        """
        Sends an existing draft by id.
        """
        r = requests.post(f"{GRAPH}/me/messages/{message_id}/send", headers=self.h, timeout=30)
        r.raise_for_status()
        return True

    def create_and_send(
        self,
        to_email: str,
        subject: str,
        body_text: str,
    ) -> Dict[str, Any]:
        """
        Convenience: create draft, send it, then fetch from Sent Items to recover ids.
        Returns:
          {
            "draft_id": "...",
            "conversation_id": "...",
            "internet_message_id": "...",
            "sent_message_id": "..."   # best-effort
          }
        """
        draft = self.create_draft(to_email, subject, body_text)
        draft_id = draft.get("id")
        conversation_id = draft.get("conversationId")

        self.send_draft(draft_id)

        # Best-effort: fetch from Sent Items by draft_id is not directly supported.
        # Instead, query Sent Items for very recent messages matching subject + recipient.
        sent = self._find_recent_sent(to_email=to_email, subject=subject)

        return {
            "draft_id": draft_id,
            "conversation_id": conversation_id or (sent.get("conversationId") if sent else None),
            "internet_message_id": (sent.get("internetMessageId") if sent else None),
            "sent_message_id": (sent.get("id") if sent else None),
        }

    # ------------------------------------------------------------------
    # Reply tracking helpers
    # ------------------------------------------------------------------
    def list_inbox_since(
        self,
        since_iso: str,
        *,
        top: int = 25,
        select: str = "id,subject,from,receivedDateTime,conversationId,internetMessageId,bodyPreview",
    ) -> Dict[str, Any]:
        """
        List messages received since timestamp (ISO 8601).
        """
        params = {
            "$top": str(top),
            "$select": select,
            "$orderby": "receivedDateTime desc",
            "$filter": f"receivedDateTime ge {since_iso}",
        }
        r = requests.get(f"{GRAPH}/me/mailFolders/Inbox/messages", headers=self.h, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def list_inbox_by_conversation(
        self,
        conversation_id: str,
        *,
        top: int = 25,
        select: str = "id,subject,from,receivedDateTime,conversationId,internetMessageId,bodyPreview",
    ) -> Dict[str, Any]:
        params = {
            "$top": str(top),
            "$select": select,
            "$orderby": "receivedDateTime desc",
            "$filter": f"conversationId eq '{conversation_id}'",
        }
        r = requests.get(f"{GRAPH}/me/mailFolders/Inbox/messages", headers=self.h, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Internal: best-effort sent lookup
    # ------------------------------------------------------------------
    def _find_recent_sent(self, to_email: str, subject: str, minutes: int = 10) -> Optional[Dict[str, Any]]:
        """
        Attempts to find a very recent sent message matching recipient + subject.
        Not perfect, but good enough for MVP; later we can store draft_id and
        use Graph change notifications/local delta queries.
        """
        # Graph filter on subject exact match can be finicky; keep it simple.
        # We'll pull recent sent items and match in code.
        params = {
            "$top": "25",
            "$select": "id,subject,conversationId,internetMessageId,toRecipients,sentDateTime",
            "$orderby": "sentDateTime desc",
        }
        r = requests.get(f"{GRAPH}/me/mailFolders/SentItems/messages", headers=self.h, params=params, timeout=30)
        r.raise_for_status()
        items = r.json().get("value", [])

        subj = (subject or "").strip().lower()
        target = (to_email or "").strip().lower()

        for m in items:
            ms = (m.get("subject") or "").strip().lower()
            if subj and ms != subj:
                continue
            tos = m.get("toRecipients") or []
            to_addrs = []
            for t in tos:
                addr = (((t or {}).get("emailAddress") or {}).get("address") or "").strip().lower()
                if addr:
                    to_addrs.append(addr)
            if target and target not in to_addrs:
                continue
            return m

        return None
    def list_recent_inbox_messages(self, *, minutes: int = 10, top: int = 50) -> list[dict]:
            since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            data = self.list_inbox_since(_utc_iso(since), top=top)
            return data.get("value", [])
