import { CommonModule } from '@angular/common';
import { Component, Input, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { FileUploadComponent } from '../../components/form/file-upload/file-upload.component';
import { WeeklyAvailabilityComponent } from "../../components/form/weekly-availability/weekly-availability.component";
import { ErrorMessageComponent } from "../../components/error-message/error-message.component";
import { ApiService } from '../../shared/services/api.service';
import { AppService } from '../../services/core/app/app.service';

interface Address {
  street: string;
  city: string;
  country: string;
  postalCode: string;
}

interface Identification {
  idType: string;
  idNumber: string;
  document?: File | null;
}

interface SecurityLicense {
  licenseNumber: string;
  issuingAuthority: string;
  expiryDate: string;
  document?: File | null;
}

interface WeeklyAvailability {
  Monday: string[];
  Tuesday: string[];
  Wednesday: string[];
  Thursday: string[];
  Friday: string[];
  Saturday: string[];
  Sunday: string[];
}

interface Guard {
  name: string;
  contact: string;
  dob: string;
  address: Address;
  identification: Identification;
  securityLicense: SecurityLicense;
  operationalRadius: number | null;
  weeklyAvailability: WeeklyAvailability;
}

@Component({
  selector: 'app-guard-setting',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    BaseInputComponent,
    FileUploadComponent,
    WeeklyAvailabilityComponent,
    ErrorMessageComponent
  ],
  templateUrl: './guard-setting.component.html',
  styleUrls: ['./guard-setting.component.css']
})
export class GuardSettingComponent implements OnInit {

  @Input() guardData?: Guard;

  isEditMode = false;

  guardFormModel: Guard = {
    name: '',
    contact: '',
    dob: '',
    address: {
      street: '',
      city: '',
      country: '',
      postalCode: ''
    },
    identification: {
      idType: 'passport',
      idNumber: '',
      document: null
    },
    securityLicense: {
      licenseNumber: '',
      issuingAuthority: '',
      expiryDate: '',
      document: null
    },
    operationalRadius: null,
    weeklyAvailability: {
      Monday: [],
      Tuesday: [],
      Wednesday: [],
      Thursday: [],
      Friday: [],
      Saturday: [],
      Sunday: []
    }
  };


  guardErrors: any = {};

  constructor(
    private apiService: ApiService,
    private router: Router,
    private appService: AppService
  ) {}

  ngOnInit(): void {
    if (this.guardData && this.hasGuardData(this.guardData)) {
      this.guardFormModel = JSON.parse(JSON.stringify(this.guardData));
      this.isEditMode = true;
    } else {
      this.isEditMode = false;
    }
  }

  hasGuardData(data: Guard): boolean {
    return !!(
      data.name.trim() ||
      data.contact.trim() ||
      data.dob ||
      data.address.street.trim() ||
      data.identification.idNumber.trim() ||
      data.securityLicense.licenseNumber.trim() ||
      data.operationalRadius != null ||
      Object.values(data.weeklyAvailability).some(day => day.length > 0)
    );
  }

  validateGuardForm(): boolean {
    this.guardErrors = {};

    // Name
    if (!this.guardFormModel.name.trim()) {
      this.guardErrors.name = 'Name is required.';
    } else if (/[^a-zA-Z ]/.test(this.guardFormModel.name)) {
      this.guardErrors.name = 'Name can only contain letters and spaces.';
    }

    // Contact (allow international, 10-15 digits after stripping formatting)
    if (!this.guardFormModel.contact.trim()) {
      this.guardErrors.contact = 'Contact Number is required.';
    } else {
      const contactDigits = this.guardFormModel.contact.replace(/[^0-9]/g, '');
      if (contactDigits.length < 10 || contactDigits.length > 15) {
        this.guardErrors.contact = 'Phone number must be 10-15 digits.';
      }
    }

    // Address
    if (!this.guardFormModel.address.street.trim()) {
      this.guardErrors.addressStreet = 'Street address is required.';
    }
    if (!this.guardFormModel.address.city.trim()) {
      this.guardErrors.addressCity = 'City is required.';
    }
    if (!this.guardFormModel.address.country.trim()) {
      this.guardErrors.addressCountry = 'Country is required.';
    }
    if (!this.guardFormModel.address.postalCode.trim()) {
      this.guardErrors.addressPostalCode = 'Postal code is required.';
    }

    // Identification
    if (!this.guardFormModel.identification.idNumber.trim()) {
      this.guardErrors.idNumber = 'ID number is required.';
    } else {
      const idNormalized = this.guardFormModel.identification.idNumber.replace(/[^A-Za-z0-9]/g, '');
      if (idNormalized.length < 4 || idNormalized.length > 32) {
        this.guardErrors.idNumber = 'ID number must be 4-32 letters or numbers (hyphens/slashes/spaces allowed).';
      }
    }

    // Security License
    if (!this.guardFormModel.securityLicense.licenseNumber.trim()) {
      this.guardErrors.licenseNumber = 'Security License number is required.';
    } else {
      const licenseNormalized = this.guardFormModel.securityLicense.licenseNumber.replace(/[^A-Za-z0-9]/g, '');
      if (licenseNormalized.length < 4 || licenseNormalized.length > 32) {
        this.guardErrors.licenseNumber = 'Security License must be 4-32 letters or numbers (hyphens/slashes/spaces allowed).';
      }
    }
    if (!this.guardFormModel.securityLicense.issuingAuthority.trim()) {
      this.guardErrors.issuingAuthority = 'Issuing authority is required.';
    }
    if (!this.guardFormModel.securityLicense.expiryDate) {
      this.guardErrors.expiryDate = 'Expiry date is required.';
    }

    // Operational Radius
    if (
      this.guardFormModel.operationalRadius != null &&
      (isNaN(this.guardFormModel.operationalRadius) ||
        this.guardFormModel.operationalRadius < 1)
    ) {
      this.guardErrors.operationalRadius = 'Operational radius must be at least 1 mile.';
    }

    return Object.keys(this.guardErrors).length === 0;
  }

  submitGuardForm(): void {
    if (!this.validateGuardForm()) {
      return;
    }

    const tenantUpdatePayload = {
      tenant_type: 'guard',
      profile: {
        name: this.guardFormModel.name,
        contact: this.guardFormModel.contact,
        date_of_birth: this.guardFormModel.dob,
        address: this.guardFormModel.address,
        identification: {
          id_type: this.guardFormModel.identification.idType,
          id_number: this.guardFormModel.identification.idNumber
        },
        security_license: {
          license_number: this.guardFormModel.securityLicense.licenseNumber,
          issuing_authority: this.guardFormModel.securityLicense.issuingAuthority,
          expiry_date: this.guardFormModel.securityLicense.expiryDate
        },
        operational_radius: this.guardFormModel.operationalRadius,
        weekly_availability: this.guardFormModel.weeklyAvailability
      },
      status: 'active'
    };

    this.apiService.put('tenant', tenantUpdatePayload).subscribe({
      next: (response) => {
        console.log('Guard profile submitted successfully', response);
        this.appService.setTenantStatus('active', false);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        console.error('Error submitting guard profile:', err);
        this.guardErrors.submit = err?.error?.detail || 'Failed to submit guard profile.';
      }
    });
  }
}