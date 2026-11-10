import { v4 as uuidv4 } from "uuid";

export interface NotificationItem {
  notification_id: string;
  evidence_id: string;
  decision: "APPROVED" | "RETAKE_REQUESTED";
  notes: string;
  is_read: boolean;
  action_required: boolean;
  received_at: string;
}

export class NotificationInboxService {
  private notifications: NotificationItem[] = [];

  receiveNotification(evidenceId: string, decision: "APPROVED" | "RETAKE_REQUESTED", notes: string): string {
    const notifId = uuidv4 ? uuidv4() : `notif-${Date.now()}`;
    const item: NotificationItem = {
      notification_id: notifId,
      evidence_id: evidenceId,
      decision,
      notes,
      is_read: false,
      action_required: decision === "RETAKE_REQUESTED",
      received_at: new Date().toISOString(),
    };
    this.notifications.push(item);
    return notifId;
  }

  markRead(notificationId: string): void {
    const item = this.notifications.find((n) => n.notification_id === notificationId);
    if (item) {
      item.is_read = true;
    }
  }

  getUnreadCount(): number {
    return this.notifications.filter((n) => !n.is_read).length;
  }

  getNotifications(): NotificationItem[] {
    return [...this.notifications];
  }
}

export const notificationService = new NotificationInboxService();

