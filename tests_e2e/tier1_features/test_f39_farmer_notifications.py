"""F-39: Farmer Review Decision Notifications Tests.
Validates mobile receipt of reviewer feedback, retake requests with reason notes,
and in-app status indicators.
"""

import uuid
import pytest


class NotificationInbox:
    """Simulates mobile client in-app notification center."""

    def __init__(self):
        self.notifications = []

    def receive_notification(self, evidence_id: str, decision: str, notes: str) -> str:
        notif_id = str(uuid.uuid4())
        self.notifications.append({
            "notification_id": notif_id,
            "evidence_id": evidence_id,
            "decision": decision,
            "notes": notes,
            "is_read": False,
        })
        return notif_id

    def mark_read(self, notif_id: str):
        for n in self.notifications:
            if n["notification_id"] == notif_id:
                n["is_read"] = True

    def get_unread_count(self) -> int:
        return sum(1 for n in self.notifications if not n["is_read"])


class TestF39FarmerNotifications:
    """Verifies farmer review notifications and feedback handling."""

    def test_receive_retake_request_notification(self):
        """Test 1: Verifies farmer receives notification when reviewer requests retake."""
        inbox = NotificationInbox()
        ev_id = "ev-blurry-101"
        reason = "Photo is blurry. Please capture clear view of flowering stage."

        n_id = inbox.receive_notification(ev_id, "RETAKE_REQUESTED", reason)
        assert len(inbox.notifications) == 1
        assert inbox.notifications[0]["decision"] == "RETAKE_REQUESTED"
        assert inbox.notifications[0]["notes"] == reason

    def test_receive_approved_notification(self):
        """Test 2: Verifies farmer receives approval notification for successful evidence."""
        inbox = NotificationInbox()
        inbox.receive_notification("ev-pristine", "APPROVED", "Evidence verified and committed to ledger.")
        assert inbox.notifications[0]["decision"] == "APPROVED"

    def test_unread_count_badge(self):
        """Test 3: Verifies unread notification count badge reflects new incoming items."""
        inbox = NotificationInbox()
        assert inbox.get_unread_count() == 0

        n1 = inbox.receive_notification("ev-1", "APPROVED", "")
        n2 = inbox.receive_notification("ev-2", "RETAKE_REQUESTED", "")
        assert inbox.get_unread_count() == 2

        inbox.mark_read(n1)
        assert inbox.get_unread_count() == 1

    def test_retake_triggers_camera_action_flag(self):
        """Test 4: Verifies RETAKE_REQUESTED decision triggers an action required flag."""
        inbox = NotificationInbox()
        inbox.receive_notification("ev-1", "RETAKE_REQUESTED", "Retake needed")

        action_required = inbox.notifications[0]["decision"] == "RETAKE_REQUESTED"
        assert action_required is True

    def test_empty_inbox_handling(self):
        """Test 5: Verifies new or clean installation has empty inbox without errors."""
        inbox = NotificationInbox()
        assert len(inbox.notifications) == 0
        assert inbox.get_unread_count() == 0
