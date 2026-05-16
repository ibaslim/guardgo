import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

import { IconComponent } from '../icon/icon.component';
import type { IconName } from '../icon/icon.component';

@Component({
  selector: 'app-list-state-panel',
  standalone: true,
  imports: [CommonModule, IconComponent],
  templateUrl: './list-state-panel.component.html',
})
export class ListStatePanelComponent {
  @Input() mode: 'loading' | 'empty' = 'loading';
  @Input() loadingRows = 3;
  @Input() icon: IconName = 'file-text';
  @Input() title = '';
  @Input() message = '';

  get rows(): number[] {
    return Array.from({ length: Math.max(1, this.loadingRows) }, (_, index) => index + 1);
  }
}
