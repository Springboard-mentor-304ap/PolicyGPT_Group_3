import {
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  Output,
  inject,
} from '@angular/core';
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
  private readonly elementRef = inject(ElementRef<HTMLElement>);

  @Input({ required: true }) unreadCount = 0;
  @Input({ required: true }) items: NotificationItem[] = [];
  @Input({ required: true }) open = false;

  @Output() toggle = new EventEmitter<void>();
  @Output() close = new EventEmitter<void>();
  @Output() markRead = new EventEmitter<NotificationItem>();
  @Output() markAllRead = new EventEmitter<void>();

  /**
   * Close the dropdown when the user clicks anywhere outside the bell.
   *
   * The host element wraps both the bell and the dropdown, so a click on
   * either one is "inside" and never closes it — which also means the click
   * that opens the dropdown cannot immediately close it again. Mark-as-read
   * actions stay open as well; only genuinely external clicks (or navigation)
   * dismiss the panel.
   */
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (!this.open) {
      return;
    }

    const target = event.target as Node | null;

    if (target && this.elementRef.nativeElement.contains(target)) {
      return;
    }

    this.close.emit();
  }
}
