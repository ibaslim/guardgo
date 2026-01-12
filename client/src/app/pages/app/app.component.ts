import { Component, signal } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { ErrorStoreService } from '../../shared/services/error-store.service';
import { filter, map, Observable } from 'rxjs';
import { NgIf } from '@angular/common';
import { AppService } from '../../services/core/app/app.service';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { MessageNotificationComponent } from '../../shared/partials/message-notification/message-notification.component';
import { ThemeService } from '../../services/theme/theme.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, NgIf, FormsModule, ReactiveFormsModule, MessageNotificationComponent],
  templateUrl: './app.component.html',
})
export class AppComponent {
  currentRoute = signal('');
  error$: Observable<boolean>;
  isVisible = true;

  constructor(
    private router: Router, 
    private errorStore: ErrorStoreService, 
    protected appService: AppService,
    private themeService: ThemeService
  ) {
    // ThemeService constructor handles theme initialization
    this.error$ = this.errorStore.error$;

    this.router.events.pipe(filter(event => event instanceof NavigationEnd), map(() => {
      const path = this.router.parseUrl(this.router.url).root.children['primary']?.segments.map(s => s.path).join('/') || '';
      return `/${path}`;
    })).subscribe((path) => {
      this.currentRoute.set(path);
    });
  }
}
