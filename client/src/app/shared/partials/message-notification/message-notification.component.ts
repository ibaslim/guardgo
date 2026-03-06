import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { CommonModule } from '@angular/common';
import { MessageNotificationService } from '../../../services/message_notification/message-notification.service';
import { IconComponent } from '../../../components/icon/icon.component';

@Component({
  selector: 'app-message-notification',
  imports: [NgIf, CommonModule, IconComponent],
  templateUrl: './message-notification.component.html',
  styleUrl: './message-notification.component.css'
})
export class MessageNotificationComponent {
  constructor(protected notificationService: MessageNotificationService) {}

  trackByToastId(_: number, toast: { id: string }): string {
    return toast.id;
  }

  dismiss(id: string): void {
    this.notificationService.dismiss(id);
  }

  iconByType(type: string): 'check-circle' | 'alert-circle' | 'alert-triangle' | 'info' {
    if (type === 'success') return 'check-circle';
    if (type === 'warning') return 'alert-triangle';
    if (type === 'info') return 'info';
    return 'alert-circle';
  }
}
