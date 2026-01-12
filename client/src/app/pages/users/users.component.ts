import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  status: string;
  joinedDate: string;
  initials: string;
  color: string;
}

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './users.component.html',
})
export class UsersComponent {
  stats = [
    { name: 'Total Users', value: '2,651', change: '+12%', changeType: 'increase' },
    { name: 'Active Users', value: '1,892', change: '+8%', changeType: 'increase' },
    { name: 'New This Month', value: '247', change: '+24%', changeType: 'increase' },
    { name: 'User Growth', value: '+15%', change: '+3%', changeType: 'increase' },
  ];

  users: User[] = [
    { id: 1, name: 'John Smith', email: 'john.smith@example.com', role: 'Admin', status: 'Active', joinedDate: '2024-01-15', initials: 'JS', color: 'bg-blue-500' },
    { id: 2, name: 'Sarah Johnson', email: 'sarah.j@example.com', role: 'User', status: 'Active', joinedDate: '2024-02-20', initials: 'SJ', color: 'bg-green-500' },
    { id: 3, name: 'Mike Williams', email: 'mike.w@example.com', role: 'User', status: 'Active', joinedDate: '2024-03-10', initials: 'MW', color: 'bg-purple-500' },
    { id: 4, name: 'Emma Davis', email: 'emma.davis@example.com', role: 'Admin', status: 'Active', joinedDate: '2024-01-25', initials: 'ED', color: 'bg-pink-500' },
    { id: 5, name: 'Robert Brown', email: 'rob.brown@example.com', role: 'User', status: 'Inactive', joinedDate: '2023-12-05', initials: 'RB', color: 'bg-yellow-500' },
    { id: 6, name: 'Lisa Anderson', email: 'lisa.a@example.com', role: 'Guest', status: 'Active', joinedDate: '2024-04-01', initials: 'LA', color: 'bg-red-500' },
    { id: 7, name: 'David Miller', email: 'david.m@example.com', role: 'User', status: 'Active', joinedDate: '2024-02-14', initials: 'DM', color: 'bg-indigo-500' },
    { id: 8, name: 'Jennifer Wilson', email: 'jen.wilson@example.com', role: 'Admin', status: 'Active', joinedDate: '2024-01-08', initials: 'JW', color: 'bg-teal-500' },
    { id: 9, name: 'Tom Garcia', email: 'tom.garcia@example.com', role: 'User', status: 'Inactive', joinedDate: '2023-11-20', initials: 'TG', color: 'bg-orange-500' },
    { id: 10, name: 'Amy Martinez', email: 'amy.m@example.com', role: 'Guest', status: 'Active', joinedDate: '2024-03-28', initials: 'AM', color: 'bg-cyan-500' },
  ];
}
