import { Injectable } from '@angular/core';
import { Router } from '@angular/router';

export interface User {
  email: string;
}

@Injectable({
  providedIn: 'root',
})
export class Auth {
  private currentUser: User | null = null;

  constructor(private router: Router) {
    // Check if user is already logged in (from localStorage)
    try {
      const savedUser = localStorage.getItem('currentUser');
      if (savedUser) {
        const parsed = JSON.parse(savedUser);
        // Validate the structure of the parsed data
        if (parsed && typeof parsed.email === 'string') {
          this.currentUser = parsed;
        }
      }
    } catch (error) {
      // If parsing fails, clear invalid data
      localStorage.removeItem('currentUser');
    }
  }

  register(email: string, password: string): boolean {
    // In a real app, this would call an API
    // For now, just store the user
    this.currentUser = { email };
    localStorage.setItem('currentUser', JSON.stringify(this.currentUser));
    return true;
  }

  login(email: string, password: string): boolean {
    // In a real app, this would validate against an API
    // For now, just check if credentials are provided
    if (email && password) {
      this.currentUser = { email };
      localStorage.setItem('currentUser', JSON.stringify(this.currentUser));
      return true;
    }
    return false;
  }

  logout(): void {
    this.currentUser = null;
    localStorage.removeItem('currentUser');
    this.router.navigate(['/login']);
  }

  getCurrentUser(): User | null {
    return this.currentUser;
  }

  isAuthenticated(): boolean {
    return this.currentUser !== null;
  }
}
