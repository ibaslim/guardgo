import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type BannerType = 'pending' | 'error' | 'success' | 'warning' | 'maintenance' | 'info';

@Component({
  selector: 'app-big-banner',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './big-banner.component.html',
  styleUrls: ['./big-banner.component.css']
})
export class BigBannerComponent {
  @Input() type: BannerType = 'info';
  @Input() title: string = '';
  @Input() message: string = '';

  getInfoBoxColorClass(): string {
    switch (this.type) {
      case 'pending': return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800';
      case 'error': return 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800';
      case 'success': return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800';
      case 'warning': return 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800';
      case 'maintenance': return 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800';
      case 'info': return 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800';
      default: return 'bg-gray-50 dark:bg-gray-900/20 border-gray-200 dark:border-gray-800';
    }
  }
}
