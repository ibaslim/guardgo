import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-button',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './button.component.html'
})
export class ButtonComponent {
  @Input() type: 'primary' | 'secondary' | 'success' | 'danger' | 'warning' | 'info' | 'outline' | 'link' = 'primary';
  @Input() htmlType: 'button' | 'submit' | 'reset' = 'button';
  @Input() disabled = false;
  @Input() label = '';
  @Input() fullWidth = false;
  @Input() size: 'sm' | 'md' | 'lg' = 'md';
  @Input() customClass = '';
  @Input() ariaLabel = '';
  @Input() loading = false;

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
}
