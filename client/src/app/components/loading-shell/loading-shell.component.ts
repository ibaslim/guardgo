import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { PlaceloadComponent } from '../placeload/placeload.component';

@Component({
  selector: 'app-loading-shell',
  standalone: true,
  imports: [CommonModule, PlaceloadComponent],
  templateUrl: './loading-shell.component.html'
})
export class LoadingShellComponent {
  @Input() variant: 'detail' | 'form' | 'list' = 'form';
}
