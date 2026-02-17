import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-placeload',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './placeload.component.html'
})
export class PlaceloadComponent {
  @Input() width = '100%';
  @Input() height = '1rem';
  @Input() rounded = 'md';
}