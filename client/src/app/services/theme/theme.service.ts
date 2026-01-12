import { Injectable, signal } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  private darkModeSignal = signal<boolean>(false);
  private readonly DEFAULT_THEME = 'dark';

  constructor() {
    this.initializeTheme();
  }

  private initializeTheme() {
    // Initialize from localStorage (client-side only)
    if (typeof localStorage !== 'undefined' && typeof document !== 'undefined') {
      let savedTheme = localStorage.getItem('theme');
      
      // Handle legacy theme values (one-time migration per user)
      if (savedTheme === 'dark-theme') {
        savedTheme = 'dark';
        localStorage.setItem('theme', savedTheme);
      } else if (savedTheme === 'light-theme') {
        savedTheme = 'light';
        localStorage.setItem('theme', savedTheme);
      }
      
      // Default to dark if no theme is set (null or undefined)
      const isDark = savedTheme === 'dark' || savedTheme == null;
      this.darkModeSignal.set(isDark);
      
      // Apply theme to DOM
      this.applyThemeToDOM(isDark);
    }
  }

  private applyThemeToDOM(isDark: boolean) {
    if (typeof document !== 'undefined') {
      if (isDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
  }

  isDarkMode() {
    return this.darkModeSignal();
  }

  toggleTheme() {
    const newMode = !this.darkModeSignal();
    this.darkModeSignal.set(newMode);
    this.applyThemeToDOM(newMode);

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('theme', newMode ? 'dark' : 'light');
    }
  }
}
