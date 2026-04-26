import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { LoaderComponent } from '../loader';
import { LoadingFeedbackService } from '../../shared/services/loading-feedback.service';

@Component({
  selector: 'app-button',
  standalone: true,
  imports: [CommonModule, LoaderComponent],
  templateUrl: './button.component.html'
})
export class ButtonComponent {
  private readonly loadingFeedback = inject(LoadingFeedbackService);

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
  @Input() loadingScope = '';
  @Input() loadingLabel = 'Loading...';
  @Input() iconOnly = false;
  @Input() hasIcon = false;

  get showIconSlot(): boolean {
    return this.iconOnly || this.hasIcon;
  }

  get isLoading(): boolean {
    return this.loading || (!!this.loadingScope && this.loadingFeedback.isScopeLoading(this.loadingScope));
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
    if (this.disabled || this.isLoading) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    this.pressed.emit(event);
  }
}
