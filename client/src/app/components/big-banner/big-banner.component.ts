import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type BannerType = 'pending' | 'error' | 'success' | 'warning' | 'maintenance' | 'info';
export type BannerSize = 'sm' | 'md' | 'lg' | 'xl' | 'full';

@Component({
  selector: 'app-big-banner',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './big-banner.component.html'
})
export class BigBannerComponent {
  @Input() type: BannerType = 'info';
  @Input() title: string = '';
  @Input() message: string = '';
  @Input() size: BannerSize = 'md';

  // Background color based on type
  getBackgroundClass(): string {
    switch (this.type) {
      case 'pending':
        return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800';
      case 'error':
        return 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800';
      case 'success':
        return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800';
      case 'warning':
        return 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800';
      case 'maintenance':
        return 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800';
      case 'info':
      default:
        return 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800';
    }
  }

  // Card size: width & padding
  getSizeClass(): string {
    switch (this.size) {
      case 'sm': return 'max-w-md p-4';
      case 'md': return 'max-w-2xl p-8';
      case 'lg': return 'max-w-4xl p-12';
      case 'xl': return 'max-w-5xl p-16';
      case 'full': return 'w-full h-full p-20';
      default: return 'max-w-2xl p-8';
    }
  }

  // Title font size
  getTitleClass(): string {
    switch (this.size) {
      case 'sm': return 'text-2xl';
      case 'md': return 'text-4xl';
      case 'lg': return 'text-5xl';
      case 'xl': return 'text-6xl';
      case 'full': return 'text-7xl';
      default: return 'text-4xl';
    }
  }

  // Message font size
  getMessageClass(): string {
    switch (this.size) {
      case 'sm': return 'text-sm';
      case 'md': return 'text-lg';
      case 'lg': return 'text-xl';
      case 'xl': return 'text-2xl';
      case 'full': return 'text-3xl';
      default: return 'text-lg';
    }
  }
}
