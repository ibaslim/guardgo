import { Component } from '@angular/core';

@Component({
  selector: 'app-not-found',
  standalone: true,
  template: `
    <div class="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <h1 class="text-7xl font-extrabold text-blue-600 dark:text-blue-400 mb-4">404</h1>
      <h2 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Page Not Found</h2>
      <p class="text-gray-500 dark:text-gray-400 mb-6">Sorry, the page you are looking for does not exist or has been moved.</p>
      <a routerLink="/dashboard/overview" class="inline-block px-6 py-2 bg-blue-600 text-white dark:bg-blue-500 dark:text-white rounded hover:bg-blue-700 dark:hover:bg-blue-400 transition">Go to Dashboard</a>
    </div>
  `
})
export class NotFoundComponent {}
