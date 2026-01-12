import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './analytics.component.html',
})
export class AnalyticsComponent implements OnInit {
  metrics = [
    { name: 'Page Views', value: '45,231', change: '+12.3%', changeType: 'increase' },
    { name: 'Sessions', value: '12,893', change: '+8.1%', changeType: 'increase' },
    { name: 'Bounce Rate', value: '32.4%', change: '-2.5%', changeType: 'decrease' },
    { name: 'Avg. Duration', value: '3m 24s', change: '+15.2%', changeType: 'increase' },
  ];

  recentTrends = [
    { date: '2024-01-10', pageViews: 5234, sessions: 1432, bounceRate: 31.2 },
    { date: '2024-01-09', pageViews: 4892, sessions: 1389, bounceRate: 33.1 },
    { date: '2024-01-08', pageViews: 5123, sessions: 1456, bounceRate: 30.8 },
    { date: '2024-01-07', pageViews: 4756, sessions: 1312, bounceRate: 34.5 },
    { date: '2024-01-06', pageViews: 4234, sessions: 1198, bounceRate: 35.2 },
  ];

  topPages = [
    { path: '/dashboard', views: 12453, percentage: 27.5 },
    { path: '/users', views: 8721, percentage: 19.3 },
    { path: '/analytics', views: 6892, percentage: 15.2 },
    { path: '/settings', views: 5234, percentage: 11.6 },
    { path: '/reports', views: 4521, percentage: 10.0 },
  ];

  constructor() {}

  ngOnInit() {}

  getChangeClass(changeType: string): string {
    if (changeType === 'increase') {
      return 'text-green-600 dark:text-green-400';
    } else if (changeType === 'decrease') {
      return 'text-red-600 dark:text-red-400';
    }
    return 'text-gray-600 dark:text-gray-400';
  }

  getBarWidth(percentage: number): string {
    return `${percentage}%`;
  }
}
