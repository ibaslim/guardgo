import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-file-input',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './file-input.component.html'
})
export class FileInputComponent {
  @Input() label: string = 'Upload File';
  @Input() accept: string = '*/*';
  @Input() disabled: boolean = false;
  @Input() type: 'primary' | 'secondary' = 'secondary';
  @Input() showIcon: boolean = true;
  @Input() customClass: string = '';
  
  @Output() fileSelected = new EventEmitter<File>();

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.fileSelected.emit(input.files[0]);
      // Reset input so same file can be selected again
      input.value = '';
    }
  }
}
