import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit } from '@angular/core';
import { Router, RouterModule } from '@angular/router';

import { IconComponent } from '../icon/icon.component';
import { NotificationsService } from '../../services/notifications/notifications.service';
import { NotificationItem } from '../../shared/model/notification/notification.model';

@Component({
  selector: 'app-notification-bell',
  standalone: true,
  imports: [CommonModule, RouterModule, IconComponent],
  templateUrl: './notification-bell.component.html'
})
export class NotificationBellComponent implements OnInit {
  isOpen = false;

  constructor(
    protected notificationsService: NotificationsService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.notificationsService.loadLatest(6).subscribe();
  }

  toggleMenu(event: MouseEvent): void {
    event.stopPropagation();
    this.isOpen = !this.isOpen;
    if (this.isOpen) {
      this.notificationsService.loadLatest(6).subscribe();
    }
  }

  closeMenu(): void {
    this.isOpen = false;
  }

  @HostListener('document:mousedown', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (!target.closest('.notification-bell-container')) {
      this.closeMenu();
    }
  }

  onOpenNotification(item: NotificationItem, event?: MouseEvent): void {
    event?.stopPropagation();
    const navigate = () => {
      if (item.action_url) {
        this.router.navigateByUrl(item.action_url).then();
      } else {
        this.router.navigate(['/dashboard/notifications']).then();
      }
      this.closeMenu();
    };

    if (!item.is_read) {
      this.notificationsService.markAsRead(item.id).subscribe({ next: () => navigate(), error: () => navigate() });
      return;
    }

    navigate();
  }

  markAllRead(event: MouseEvent): void {
    event.stopPropagation();
    this.notificationsService.markAllRead().subscribe();
  }

  viewAll(event: MouseEvent): void {
    event.stopPropagation();
    this.router.navigate(['/dashboard/notifications']).then(() => this.closeMenu());
  }

  trackById(_index: number, item: NotificationItem): string {
    return item.id;
  }

  getCategoryClasses(category: string): string {
    switch ((category || '').toLowerCase()) {
      case 'success':
        return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300';
      case 'warning':
        return 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300';
      case 'error':
        return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300';
      default:
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300';
    }
  }

  formatRelativeDate(value: string): string {
    const date = new Date(value);
    const diffMs = Date.now() - date.getTime();
    const diffMinutes = Math.max(1, Math.floor(diffMs / 60000));
    if (diffMinutes < 60) {
      return `${diffMinutes}m ago`;
    }
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) {
      return `${diffHours}h ago`;
    }
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) {
      return `${diffDays}d ago`;
    }
    return date.toLocaleDateString();
  }
}
