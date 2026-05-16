import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-drawer-action-row',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './drawer-action-row.component.html',
})
export class DrawerActionRowComponent {
  @Input() containerClass = 'flex flex-wrap justify-end gap-2';
}
