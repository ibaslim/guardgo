import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-validation-message',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './validation-message.component.html',
})
export class ValidationMessageComponent {
  @Input() message: string | null | undefined = null;
  @Input() className = 'mt-1 text-xs text-red-500';
}
