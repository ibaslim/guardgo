import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { BigBannerComponent } from '../../components/big-banner/big-banner.component';
import { BannerComponent } from '../../components/banner/banner.component';

@Component({
  selector: 'app-pending-verification',
  standalone: true,
  imports: [CommonModule, BigBannerComponent, BannerComponent],
  templateUrl: './pending-verification.component.html',
})
export class PendingVerificationComponent implements OnInit {

  constructor(private router: Router) { }

  ngOnInit(): void {
  }
}
