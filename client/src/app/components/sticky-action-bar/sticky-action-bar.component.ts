import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-sticky-action-bar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './sticky-action-bar.component.html',
  styleUrls: ['./sticky-action-bar.component.scss']
})
export class StickyActionBarComponent {
  /**
   * Message to display on the left side of the action bar
   * @example "Save to continue onboarding."
   */
  @Input() message?: string;

  /**
   * Additional CSS classes for the outer sticky container
   */
  @Input() containerClass: string = '';

  /**
   * Additional CSS classes for the inner card
   */
  @Input() cardClass: string = '';
}
