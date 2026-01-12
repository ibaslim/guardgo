import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';

interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  status: 'active' | 'inactive';
  avatar: string;
}

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './users.component.html',
})
export class UsersComponent implements OnInit {
  stats = [
    { name: 'Total Users', value: '1,234', icon: 'users' },
    { name: 'Active Users', value: '892', icon: 'user-check' },
    { name: 'New This Month', value: '156', icon: 'user-plus' },
    { name: 'Pending Approval', value: '23', icon: 'clock' },
  ];

  users: User[] = [
    {
      id: 1,
      name: 'John Smith',
      email: 'john.smith@example.com',
      role: 'Administrator',
      status: 'active',
      avatar: 'JS'
    },
    {
      id: 2,
      name: 'Sarah Johnson',
      email: 'sarah.johnson@example.com',
      role: 'Manager',
      status: 'active',
      avatar: 'SJ'
    },
    {
      id: 3,
      name: 'Michael Chen',
      email: 'michael.chen@example.com',
      role: 'Developer',
      status: 'active',
      avatar: 'MC'
    },
    {
      id: 4,
      name: 'Emma Wilson',
      email: 'emma.wilson@example.com',
      role: 'Designer',
      status: 'inactive',
      avatar: 'EW'
    },
    {
      id: 5,
      name: 'David Brown',
      email: 'david.brown@example.com',
      role: 'Developer',
      status: 'active',
      avatar: 'DB'
    },
    {
      id: 6,
      name: 'Lisa Anderson',
      email: 'lisa.anderson@example.com',
      role: 'Support',
      status: 'active',
      avatar: 'LA'
    },
    {
      id: 7,
      name: 'James Taylor',
      email: 'james.taylor@example.com',
      role: 'Manager',
      status: 'active',
      avatar: 'JT'
    },
    {
      id: 8,
      name: 'Maria Garcia',
      email: 'maria.garcia@example.com',
      role: 'Developer',
      status: 'inactive',
      avatar: 'MG'
    }
  ];

  constructor() {}

  ngOnInit() {}

  getStatusClass(status: string): string {
    return status === 'active' 
      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
      : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400';
  }
}
