import { AfterViewInit, ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { NgIf } from '@angular/common';
import { Router, RouterOutlet } from '@angular/router';
import { ScrollingModule } from '@angular/cdk/scrolling';
import { AppService } from '../../services/core/app/app.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    RouterOutlet,
    ScrollingModule,
    NgIf,
  ],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements AfterViewInit, OnInit {
  isMenuOpen = true;
  animationState: any;

  constructor(private cdr: ChangeDetectorRef, public router: Router, protected appService: AppService) {
  }
  ngOnInit(): void {
    this.appService.set('isSidebarOpen', this.isMenuOpen);
  }


  prepareRoute(outlet: RouterOutlet) {
    this.animationState = outlet?.activatedRouteData?.['animation'] || null;
    return this.animationState;
  }

  isCtiGraph(): boolean {
    return this.router.url.includes('/dashboard/ctigraph');
  }

  ngAfterViewInit() {
    this.cdr.detectChanges();
  }
}
