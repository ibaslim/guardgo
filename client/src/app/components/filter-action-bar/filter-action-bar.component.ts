import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

import { ButtonComponent } from '../button/button.component';

@Component({
  selector: 'app-filter-action-bar',
  standalone: true,
  imports: [CommonModule, ButtonComponent],
  templateUrl: './filter-action-bar.component.html',
})
export class FilterActionBarComponent {
  @Input() applyLabel = 'Apply';
  @Input() clearLabel = 'Clear';
  @Input() containerClass = 'flex flex-wrap gap-2 pb-0.5 sm:justify-end';

  @Output() apply = new EventEmitter<void>();
  @Output() clear = new EventEmitter<void>();
}
