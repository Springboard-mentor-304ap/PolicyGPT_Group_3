import { Component, EventEmitter, Input, Output } from '@angular/core';
import { DatePipe } from '@angular/common';
import { NotificationItem } from '../../../../core/models/notification.models';

/**
 * Header notification bell + dropdown (unread badge, mark-as-read,
 * mark-all-as-read).
 *
 * Extracted from DashboardComponent so each component stays within
 * Angular's per-component CSS style budget. All API calls remain in
 * the parent — this component only displays the state it is given and
 * emits the user's actions.
 */
@Component({
  selector: 'app-notification-bell',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './notification-bell.component.html',
  styleUrl: './notification-bell.component.css',
})
export class NotificationBellComponent {
  @Input({ required: true }) unreadCount = 0;
  @Input({ required: true }) items: NotificationItem[] = [];
  @Input({ required: true }) open = false;

  @Output() toggle = new EventEmitter<void>();
  @Output() markRead = new EventEmitter<NotificationItem>();
  @Output() markAllRead = new EventEmitter<void>();
}
