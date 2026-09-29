export interface Notification {
  id: string;
  user_id: string;
  type: string;
  channel: string;
  title: string;
  message: string;
  related_entity_type: string | null;
  related_entity_id: string | null;
  is_read: boolean;
  sent_at: string | null;
  created_at: string;
}

export interface UnreadNotificationCount {
  unread_count: number;
}

export interface MarkAllNotificationsReadResponse {
  updated_count: number;
}