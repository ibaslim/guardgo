import { Component, OnInit } from '@angular/core';
import { ScrollingModule } from '@angular/cdk/scrolling';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    ScrollingModule,
  ],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  stats = [
    { name: 'Total Users', value: '2,651', change: '+12%', changeType: 'increase' },
    { name: 'Active Sessions', value: '1,429', change: '+8%', changeType: 'increase' },
    { name: 'Response Time', value: '24ms', change: '-4%', changeType: 'decrease' },
    { name: 'Uptime', value: '99.9%', change: '0%', changeType: 'neutral' },
  ];

  recentActivity = [
    { action: 'User login', user: 'john@example.com', time: '2 minutes ago' },
    { action: 'New registration', user: 'sarah@example.com', time: '15 minutes ago' },
    { action: 'Password reset', user: 'mike@example.com', time: '1 hour ago' },
    { action: 'Profile updated', user: 'emma@example.com', time: '2 hours ago' },
  ];

  constructor() {
  }

  ngOnInit() {
  }
}
