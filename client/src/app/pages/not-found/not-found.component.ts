import { Component } from '@angular/core';

@Component({
  selector: 'app-not-found',
  standalone: true,
  template: `
    <div class="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <h1 class="mb-4 text-6xl font-extrabold text-blue-600 dark:text-blue-400 sm:text-7xl">404</h1>
      <h2 class="mb-2 text-xl font-bold text-gray-900 dark:text-gray-100 sm:text-2xl">Page Not Found</h2>
      <p class="mb-6 max-w-md text-sm leading-6 text-gray-500 dark:text-gray-400 sm:text-base">Sorry, the page you are looking for does not exist or has been moved.</p>
      <a routerLink="/dashboard/overview" class="inline-block px-6 py-2 bg-blue-600 text-white dark:bg-blue-500 dark:text-white rounded hover:bg-blue-700 dark:hover:bg-blue-400 transition">Go to Dashboard</a>
    </div>
  `
})
export class NotFoundComponent {}
