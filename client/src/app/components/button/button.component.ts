import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-button',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './button.component.html'
})
export class ButtonComponent {
  @Output() pressed = new EventEmitter<Event>();
  @Input() type: 'primary' | 'secondary' | 'success' | 'danger' | 'warning' | 'info' | 'outline' | 'link' = 'primary';
  @Input() htmlType: 'button' | 'submit' | 'reset' = 'button';
  @Input() disabled = false;
  @Input() label = '';
  @Input() fullWidth = false;
  @Input() size: 'sm' | 'md' | 'lg' = 'md';
  @Input() customClass = '';
  @Input() ariaLabel = '';
  @Input() loading = false;
  @Input() iconOnly = false;
  @Input() hasIcon = false;

  get showIconSlot(): boolean {
    return this.iconOnly || this.hasIcon;
  }

  get sizeClass(): string {
    switch (this.size) {
      case 'sm':
        return 'px-3 py-1.5 text-xs';
      case 'lg':
        return 'px-5 py-3 text-base';
      default:
        return 'px-4 py-2 text-sm';
    }
  }

  handleClick(event: Event) {
    if (this.disabled || this.loading) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    this.pressed.emit(event);
  }
}
