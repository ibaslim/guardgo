import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ScrollingModule } from '@angular/cdk/scrolling';
import {AuthService} from "../../services/authetication/auth.service";
import {AppService} from "../../services/core/app/app.service";

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    ScrollingModule,
  ],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  userEmail = '';
  sidebarCollapsed = false;
  darkMode = false;

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

  constructor(private authService:AuthService, protected appService:AppService, private router: Router) {
    const savedTheme = localStorage.getItem('theme');
    this.darkMode = savedTheme === 'dark';

    if (this.darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }

  ngOnInit() {
  }

  toggleSidebar() {
    this.sidebarCollapsed = !this.sidebarCollapsed;
  }

  toggleDarkMode() {
    this.darkMode = !this.darkMode;
    if (this.darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }

  logout() {
    this.authService.logout();
  }
}
