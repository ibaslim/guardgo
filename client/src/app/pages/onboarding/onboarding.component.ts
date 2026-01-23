import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ClientSettingComponent } from "../client-setting/client-setting.component";
import { GuardSettingComponent } from '../guard-setting/guard-setting.component';

export interface Client {
  legalEntityName: string;
  primaryContactInfo: string;
  billingAddress: string;
  businessLogo: File | null;
  sites: { siteName: string; siteAddress: string }[];
}

export interface Guard {
  name: string;
  address: string;
  file: File | null;
  contact: string;
  dob: string;
  securityLicense: string;
  governmentId: string;
  operationalRadius: number | null;
  availability: {
    Monday: string[];
    Tuesday: string[];
    Wednesday: string[];
    Thursday: string[];
    Friday: string[];
    Saturday: string[];
    Sunday: string[];
  };
}

@Component({
  selector: 'app-onboarding',
  imports: [CommonModule,
    FormsModule, GuardSettingComponent, ClientSettingComponent],
  templateUrl: './onboarding.component.html',
  styleUrl: './onboarding.component.css'
})

export class OnboardingComponent {
  userType = 'guard'; // 'guard' or 'client'

  clientData: Client = {
    legalEntityName: 'Acme Corp',
    primaryContactInfo: '+1 289 555 1234',
    billingAddress: '123 Main Street, City',
    businessLogo: null,
    sites: [
      { siteName: 'Headquarters', siteAddress: '123 Main Street, City' },
      { siteName: 'Branch', siteAddress: '456 Secondary St, City' }
    ]
  };

  // clientData: Client = {
  //   legalEntityName: '',
  //   primaryContactInfo: '',
  //   billingAddress: '',
  //   businessLogo: null,
  //   sites: [{ siteName: '', siteAddress: '' }]
  // };

  // guardData: Guard = {
  //   name: 'Ahmed Khan',
  //   address: 'House 21, Street 5, DHA Phase 2, Lahore',
  //   file: null,
  //   contact: '+1 415 555 2671',
  //   dob: '09/15/1990',
  //   securityLicense: 'SEC789456',
  //   governmentId: '123-456-789',
  //   operationalRadius: 15,
  //   availability: {
  //     Monday: ['Morning', 'Evening'],
  //     Tuesday: ['Morning'],
  //     Wednesday: ['Night'],
  //     Thursday: ['Evening'],
  //     Friday: ['Morning', 'Night'],
  //     Saturday: [],
  //     Sunday: []
  //   }
  // };

  guardData: Guard = {
    name: '',
    address: '',
    file: null,
    contact: '',
    dob: '',
    securityLicense: '',
    governmentId: '',
    operationalRadius: null,
    availability: {
      Monday: [],
      Tuesday: [],
      Wednesday: [],
      Thursday: [],
      Friday: [],
      Saturday: [],
      Sunday: []
    }
  };

};
