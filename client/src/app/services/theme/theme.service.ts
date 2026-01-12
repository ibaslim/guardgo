import { Injectable, signal } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  private darkModeSignal = signal<boolean>(false);

  constructor() {
    // Initialize from localStorage
    const savedTheme = localStorage.getItem('theme');
    this.darkModeSignal.set(savedTheme === 'dark');
  }

  isDarkMode() {
    return this.darkModeSignal();
  }

  toggleTheme() {
    const newMode = !this.darkModeSignal();
    this.darkModeSignal.set(newMode);

    if (newMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }
}
