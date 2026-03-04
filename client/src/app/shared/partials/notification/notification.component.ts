import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { CardComponent } from '../../../components/card/card.component';

@Component({
  selector: 'app-notification',
  standalone: true,
  imports: [CardComponent],
  templateUrl: './notification.component.html'
})
export class NotificationComponent {
  title: string = 'Your Trial Has Ended';
  description: string = 'Your trial period has ended. To continue enjoying full access, please upgrade your subscription.';
  actionLabel: string = 'Back to Home';

  constructor(private router: Router) {
    const nav = this.router.getCurrentNavigation();
    const state = nav?.extras?.state;

    if (state) {
      this.title = state['title'] || this.title;
      this.description = state['description'] || this.description;
      this.actionLabel = state['actionLabel'] || this.actionLabel;
    }
  }

  goHome() {
    this.router.navigate(['/']).then();
  }
}
