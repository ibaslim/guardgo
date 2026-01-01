import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Auth } from '../../services/auth';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-dashboard',
  imports: [CommonModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit {
  userEmail = '';
  sidebarOpen = false;

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

  constructor(private authService: Auth, private router: Router) {}

  ngOnInit() {
    const user = this.authService.getCurrentUser();
    if (!user) {
      this.router.navigate(['/login']);
      return;
    }
    this.userEmail = user.email;
  }

  logout() {
    this.authService.logout();
  }

  toggleSidebar() {
    this.sidebarOpen = !this.sidebarOpen;
  }
}
