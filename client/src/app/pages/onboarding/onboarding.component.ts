import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ClientSettingComponent } from "../client-setting/client-setting.component";
import { GuardSettingComponent } from '../guard-setting/guard-setting.component';
import { ServiceProviderSettingComponent } from '../service-provider-setting/service-provider-setting.component';
import { AppService } from '../../services/core/app/app.service';

@Component({
  selector: 'app-onboarding',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    GuardSettingComponent,
    ClientSettingComponent,
    ServiceProviderSettingComponent
  ],
  templateUrl: './onboarding.component.html',
  styleUrl: './onboarding.component.css'
})
export class OnboardingComponent implements OnInit {
  userType: string = '';

  constructor(protected appService: AppService) { }

  ngOnInit() {
    const sessionData = this.appService.userSessionData();
    const tenantType = sessionData?.tenant?.tenant_type;

    if (tenantType) {
      // Map backend tenant_type to frontend userType
      const typeMap: { [key: string]: string } = {
        'GUARD': 'guard',
        'CLIENT': 'client',
        'SERVICE_PROVIDER': 'service_provider',
        'guard': 'guard',
        'client': 'client',
        'service_provider': 'service_provider'
      };
      this.userType = typeMap[tenantType] || tenantType.toLowerCase();
    }
  }
}
