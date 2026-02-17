import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

type BannerTone = 'info' | 'success' | 'warning' | 'danger' | 'neutral';

@Component({
  selector: 'app-banner',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './banner.component.html'
})
export class BannerComponent {
  @Input() tone: BannerTone = 'info';
  @Input() title = '';
  @Input() message = '';
  @Input() showIcon = true;
  @Input() containerClass = '';
  @Input() titleClass = '';
  @Input() bodyClass = '';

  get resolvedContainerClass(): string {
    const toneClass = this.toneClasses.container;
    return `rounded-lg border p-3 ${toneClass}${this.containerClass ? ' ' + this.containerClass : ''}`;
  }

  get resolvedTitleClass(): string {
    const toneClass = this.toneClasses.title;
    return `text-sm font-semibold ${toneClass}${this.titleClass ? ' ' + this.titleClass : ''}`;
  }

  get resolvedBodyClass(): string {
    const toneClass = this.toneClasses.body;
    return `text-xs ${toneClass}${this.bodyClass ? ' ' + this.bodyClass : ''}`;
  }

  get resolvedIconClass(): string {
    return `flex-shrink-0 mt-0.5 ${this.toneClasses.icon}`;
  }

  private get toneClasses() {
    switch (this.tone) {
      case 'success':
        return {
          container: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
          title: 'text-green-900 dark:text-green-200',
          body: 'text-green-800 dark:text-green-300',
          icon: 'text-green-600 dark:text-green-400'
        };
      case 'warning':
        return {
          container: 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800',
          title: 'text-yellow-900 dark:text-yellow-200',
          body: 'text-yellow-800 dark:text-yellow-300',
          icon: 'text-yellow-600 dark:text-yellow-400'
        };
      case 'danger':
        return {
          container: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800',
          title: 'text-red-900 dark:text-red-200',
          body: 'text-red-800 dark:text-red-300',
          icon: 'text-red-600 dark:text-red-400'
        };
      case 'neutral':
        return {
          container: 'bg-gray-50 dark:bg-gray-900/40 border-gray-200 dark:border-gray-700',
          title: 'text-gray-900 dark:text-gray-100',
          body: 'text-gray-700 dark:text-gray-300',
          icon: 'text-gray-600 dark:text-gray-400'
        };
      default:
        return {
          container: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
          title: 'text-blue-900 dark:text-blue-200',
          body: 'text-blue-800 dark:text-blue-300',
          icon: 'text-blue-600 dark:text-blue-400'
        };
    }
  }
}
