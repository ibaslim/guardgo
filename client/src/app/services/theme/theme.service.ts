import { Injectable, signal } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  private darkModeSignal = signal<boolean>(false);

  constructor() {
    this.initializeTheme();
  }

  initializeTheme(): void {
    try {
      const savedTheme = localStorage.getItem('theme');
      const isDark = savedTheme === 'dark';
      this.darkModeSignal.set(isDark);

      // Ensure the class is applied (it should already be from index.html script)
      if (isDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    } catch (e) {
      console.error('Failed to initialize theme:', e);
    }
  }

  isDarkMode(): boolean {
    return this.darkModeSignal();
  }

  toggleTheme(): void {
    const newDarkMode = !this.darkModeSignal();
    this.darkModeSignal.set(newDarkMode);

    if (newDarkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }

  getDarkModeSignal() {
    return this.darkModeSignal.asReadonly();
  }
}
