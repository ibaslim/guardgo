import { Component, Input, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { ApiService } from '../../shared/services/api.service';
import { ErrorMessageComponent } from '../error-message/error-message.component';
import { ButtonComponent } from '../button/button.component';
import { FileInputComponent } from '../form/file-input/file-input.component';

@Component({
  selector: 'app-profile-picture-upload',
  standalone: true,
  imports: [CommonModule, ErrorMessageComponent, ButtonComponent, FileInputComponent],
  templateUrl: './profile-picture-upload.component.html',
  styleUrls: ['./profile-picture-upload.component.scss']
})
export class ProfilePictureUploadComponent implements OnInit, OnDestroy {
  @Input() maxSizeKb: number = 500;
  @Input() title: string = 'Profile Picture';
  @Input() subtitle: string = 'Your photo helps clients recognize you.';

  profilePictureUrl: string | null = null;
  profilePictureFile: File | null = null;
  isUploadingProfilePicture = false;
  profilePictureError: string | null = null;
  
  private destroy$ = new Subject<void>();

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.loadProfilePicture();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    
    // Revoke blob URL if exists
    if (this.profilePictureUrl && this.profilePictureUrl.startsWith('blob:')) {
      URL.revokeObjectURL(this.profilePictureUrl);
    }
  }

  /**
   * Load profile picture from backend
   */
  loadProfilePicture(): void {
    this.apiService.get('tenant')
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          if (response?.id) {
            // Construct image URL from tenant ID with cache buster
            const timestamp = new Date().getTime();
            this.profilePictureUrl = `/api/s/static/tenant/${response.id}?t=${timestamp}`;
          }
        },
        error: () => {
          // No profile picture exists or error loading
          this.profilePictureUrl = null;
        }
      });
  }

  /**
   * Handle profile picture file selection
   */
  onFileSelected(file: File): void {
    this.profilePictureError = null;

    // Validate file type
    const validTypes = ['image/jpeg', 'image/jpg', 'image/png'];
    if (!validTypes.includes(file.type)) {
      this.profilePictureError = 'Only JPEG and PNG images are allowed';
      return;
    }

    // Validate file size
    const maxSize = this.maxSizeKb * 1024;
    if (file.size > maxSize) {
      this.profilePictureError = `Image must be smaller than ${this.maxSizeKb}KB`;
      return;
    }

    this.profilePictureFile = file;

    // Create preview URL
    if (this.profilePictureUrl && this.profilePictureUrl.startsWith('blob:')) {
      URL.revokeObjectURL(this.profilePictureUrl);
    }
    this.profilePictureUrl = URL.createObjectURL(file);

    // Automatically upload the picture
    this.uploadProfilePicture();
  }

  /**
   * Upload profile picture to backend
   */
  uploadProfilePicture(): void {
    if (!this.profilePictureFile) {
      return;
    }

    this.isUploadingProfilePicture = true;
    this.profilePictureError = null;

    const formData = new FormData();
    formData.append('file', this.profilePictureFile);

    this.apiService.put('tenant/image', formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.isUploadingProfilePicture = false;
          
          // Revoke the blob URL since we'll load from backend
          if (this.profilePictureUrl && this.profilePictureUrl.startsWith('blob:')) {
            URL.revokeObjectURL(this.profilePictureUrl);
          }
          
          this.profilePictureFile = null;
          
          // Small delay to ensure backend file is written
          setTimeout(() => {
            this.loadProfilePicture();
          }, 300);
        },
        error: (err) => {
          this.isUploadingProfilePicture = false;
          this.profilePictureError = err?.error?.detail || 'Failed to upload profile picture';
        }
      });
  }

  /**
   * Delete profile picture
   */
  deleteProfilePicture(): void {
    if (!confirm('Are you sure you want to delete your profile picture?')) {
      return;
    }

    this.isUploadingProfilePicture = true;
    this.profilePictureError = null;

    this.apiService.delete('tenant/image')
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.isUploadingProfilePicture = false;
          if (this.profilePictureUrl && this.profilePictureUrl.startsWith('blob:')) {
            URL.revokeObjectURL(this.profilePictureUrl);
          }
          this.profilePictureUrl = null;
          this.profilePictureFile = null;
        },
        error: (err) => {
          this.isUploadingProfilePicture = false;
          this.profilePictureError = err?.error?.detail || 'Failed to delete profile picture';
        }
      });
  }
}
