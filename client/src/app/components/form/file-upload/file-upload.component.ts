import { Component, Input, Output, EventEmitter, forwardRef, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NG_VALUE_ACCESSOR, ControlValueAccessor } from '@angular/forms';

@Component({
  selector: 'app-file-upload',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './file-upload.component.html',
  styleUrls: ['./file-upload.component.scss'],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => FileUploadComponent),
      multi: true
    }
  ]
})
export class FileUploadComponent implements ControlValueAccessor {
  @Input() label: string = '';
  @Input() required: boolean = false;
  @Input() disabled: boolean = false;
  @Input() helperText: string = '';
  @Input() errorText: string = '';
  @Input() existingFileUrl?: string; // URL to existing uploaded file
  @Input() existingFileName?: string; // Name of existing uploaded file
  @Input() accept: string = 'image/png,image/jpeg,application/pdf';
  @Input() maxFileSizeMb: number = 10;
  @Input() allowMultiple: boolean = false;
  @Input() showFileSize: boolean = true;
  @Input() enableDragDrop: boolean = true;

  @Output() fileChange = new EventEmitter<File | null>();
  value: File | null = null;
  validationError: string | null = null;
  isDragOver = false;
  onChange = (_: any) => {};
  onTouched = () => {};

  get hasExistingFile(): boolean {
    return !!(this.existingFileUrl && !this.value);
  }

  get hasNewFile(): boolean {
    return !!(this.value);
  }

  get resolvedError(): string | null {
    return this.errorText || this.validationError;
  }

  onFileChange(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files && input.files.length > 0 ? input.files[0] : null;
    this.handleFileSelection(file);
  }

  removeFile() {
    this.value = null;
    this.validationError = null;
    this.onChange(this.value);
    this.onTouched();
    this.fileChange.emit(null);
  }

  @HostListener('dragover', ['$event'])
  onDragOver(event: DragEvent) {
    if (!this.enableDragDrop || this.disabled) return;
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = true;
  }

  @HostListener('dragleave', ['$event'])
  onDragLeave(event: DragEvent) {
    if (!this.enableDragDrop || this.disabled) return;
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;
  }

  @HostListener('drop', ['$event'])
  onDrop(event: DragEvent) {
    if (!this.enableDragDrop || this.disabled) return;
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;

    const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length > 0
      ? event.dataTransfer.files[0]
      : null;
    this.handleFileSelection(file);
  }

  private handleFileSelection(file: File | null) {
    if (!file) {
      this.value = null;
      this.validationError = null;
      this.onChange(this.value);
      this.onTouched();
      this.fileChange.emit(null);
      return;
    }

    const validationError = this.validateFile(file);
    if (validationError) {
      this.value = null;
      this.validationError = validationError;
      this.onChange(this.value);
      this.onTouched();
      this.fileChange.emit(null);
      return;
    }

    this.validationError = null;
    this.value = file;
    this.onChange(this.value);
    this.onTouched();
    this.fileChange.emit(this.value);
  }

  private validateFile(file: File): string | null {
    const maxBytes = this.maxFileSizeMb * 1024 * 1024;
    if (file.size > maxBytes) {
      return `File size exceeds ${this.maxFileSizeMb}MB.`;
    }

    if (this.accept) {
      const allowed = this.accept.split(',').map(type => type.trim()).filter(Boolean);
      if (allowed.length > 0) {
        const isAllowed = allowed.some(type => {
          if (type.endsWith('/*')) {
            const prefix = type.replace('/*', '/');
            return file.type.startsWith(prefix);
          }
          return file.type === type || file.name.toLowerCase().endsWith(type.toLowerCase());
        });
        if (!isAllowed) {
          return 'File type is not allowed.';
        }
      }
    }

    return null;
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  }

  writeValue(value: File | null): void {
    this.value = value;
  }
  registerOnChange(fn: any): void {
    this.onChange = fn;
  }
  registerOnTouched(fn: any): void {
    this.onTouched = fn;
  }
  setDisabledState?(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }
}
