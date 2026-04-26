import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { LoadingFeedbackService } from '../../shared/services/loading-feedback.service';

@Component({
  selector: 'app-global-loading-bar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './global-loading-bar.component.html'
})
export class GlobalLoadingBarComponent {
  protected readonly loading = inject(LoadingFeedbackService);
}
