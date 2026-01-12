import { Injectable, signal } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  private darkModeSignal = signal<boolean>(false);

  constructor() {
    // Initialize from localStorage (client-side only)
    if (typeof localStorage !== 'undefined') {
      const savedTheme = localStorage.getItem('theme');
      this.darkModeSignal.set(savedTheme === 'dark');
    }
  }

  isDarkMode() {
    return this.darkModeSignal();
  }

  toggleTheme() {
    const newMode = !this.darkModeSignal();
    this.darkModeSignal.set(newMode);

    if (typeof document !== 'undefined') {
      if (newMode) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('theme', newMode ? 'dark' : 'light');
    }
  }
}
