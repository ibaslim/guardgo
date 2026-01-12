import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

interface TopPage {
  path: string;
  views: number;
  change: string;
}

interface TrafficSource {
  name: string;
  visitors: number;
  percentage: number;
  color: string;
}

interface Activity {
  page: string;
  views: number;
  time: string;
}

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './analytics.component.html',
})
export class AnalyticsComponent {
  metrics = [
    { name: 'Page Views', value: '45,231', change: '+18%', changeType: 'increase' },
    { name: 'Sessions', value: '12,847', change: '+12%', changeType: 'increase' },
    { name: 'Bounce Rate', value: '42.3%', change: '-5%', changeType: 'decrease' },
    { name: 'Avg. Session Duration', value: '3m 24s', change: '+8%', changeType: 'increase' },
  ];

  topPages: TopPage[] = [
    { path: '/dashboard', views: 8942, change: '+12%' },
    { path: '/users', views: 6521, change: '+8%' },
    { path: '/analytics', views: 5234, change: '+15%' },
    { path: '/settings', views: 3891, change: '+5%' },
    { path: '/reports', views: 2847, change: '+22%' },
  ];

  trafficSources: TrafficSource[] = [
    { name: 'Direct', visitors: 5429, percentage: 42.3, color: 'bg-blue-500' },
    { name: 'Organic', visitors: 3821, percentage: 29.7, color: 'bg-green-500' },
    { name: 'Referral', visitors: 2156, percentage: 16.8, color: 'bg-purple-500' },
    { name: 'Social', visitors: 1441, percentage: 11.2, color: 'bg-pink-500' },
  ];

  recentActivity: Activity[] = [
    { page: '/dashboard/overview', views: 142, time: '2 minutes ago' },
    { page: '/users/profile', views: 98, time: '5 minutes ago' },
    { page: '/analytics/reports', views: 76, time: '12 minutes ago' },
    { page: '/settings/account', views: 54, time: '18 minutes ago' },
    { page: '/dashboard/users', views: 43, time: '25 minutes ago' },
    { page: '/reports/monthly', views: 31, time: '32 minutes ago' },
  ];
}
