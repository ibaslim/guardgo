import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { CommonModule } from '@angular/common';
import { MessageNotificationService } from '../../../services/message_notification/message-notification.service';

@Component({
  selector: 'app-message-notification',
  imports: [NgIf, CommonModule],
  templateUrl: './message-notification.component.html'
})
export class MessageNotificationComponent {
  constructor(protected notificationService: MessageNotificationService) {}

  get messageValue(): string | null {
    const m = this.notificationService.message();
    if (m) {
      try { console.debug('[MessageNotificationComponent] rendering message:', m); } catch (e) {}
    }
    return m;
  }
}
