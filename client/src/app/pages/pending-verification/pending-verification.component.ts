import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { BigBannerComponent } from '../../components/big-banner/big-banner.component';
import { AppService } from '../../services/core/app/app.service';

@Component({
  selector: 'app-pending-verification',
  standalone: true,
  imports: [CommonModule, BigBannerComponent],
  templateUrl: './pending-verification.component.html',
})
export class PendingVerificationComponent implements OnInit {
  userEmail: string = '';
  userName: string = '';
  additionalInfoHtml!: SafeHtml;

  constructor(
    private appService: AppService,
    private router: Router,
    private sanitizer: DomSanitizer
  ) { }

  ngOnInit(): void {
    const session = this.appService.userSessionData();
    this.userEmail = session?.user?.email || '';
    this.userName = session?.user?.username || '';
    const tenantStatus = session?.tenant?.status;

    // Only redirect if the user should NOT see pending-verification
    if (!tenantStatus || tenantStatus === 'new' || tenantStatus === 'incomplete') {
      this.router.navigate(['/dashboard']);
    }

    this.additionalInfoHtml = this.sanitizer.bypassSecurityTrustHtml(this.getAdditionalInfo());
  }

  private getAdditionalInfo(): string {
    return `
      <h4 class="text-sm font-semibold mb-1">What happens next?</h4>
      <ul class="text-sm space-y-1 list-disc list-inside">
        <li>Our team will review your submitted information</li>
        <li>You'll receive an email notification once approved</li>
        <li>Once approved, you can log in and access your dashboard</li>
      </ul>
    `;
  }
}
