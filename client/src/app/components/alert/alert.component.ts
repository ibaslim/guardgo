import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-alert',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './alert.component.html'
})
export class AlertComponent {
  @Input() type: 'success' | 'error' | 'info' | 'warning' = 'info';
  @Input() message = '';
  @Input() closable = true;
  @Output() closed = new EventEmitter<void>();
  closedState = false;

  close() {
    this.closedState = true;
    this.closed.emit();
  }
}
