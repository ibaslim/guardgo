import { CommonModule } from '@angular/common';
import { Component, Input, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { TextareaComponent } from '../../components/form/textarea/textarea.component';
import { FileUploadComponent } from '../../components/form/file-upload/file-upload.component';
import { WeeklyAvailabilityComponent } from "../../components/form/weekly-availability/weekly-availability.component";
import { ErrorMessageComponent } from "../../components/error-message/error-message.component";
import { Guard } from '../onboarding/onboarding.component';

@Component({
  selector: 'app-guard-setting',
  imports: [
    CommonModule,
    FormsModule,
    BaseInputComponent,
    TextareaComponent,
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

  guardErrors: any = {};

  ngOnInit(): void {
    if (this.guardData && this.hasGuardData(this.guardData)) {
      // Deep copy so editing doesn't mutate parent data
      this.guardFormModel = JSON.parse(JSON.stringify(this.guardData));
      this.isEditMode = true;
    } else {
      this.isEditMode = false;
    }
  }

  /** Checks whether guardData actually contains real data */
  hasGuardData(data: Guard): boolean {
    return !!(
      data.name.trim() ||
      data.address.trim() ||
      data.contact.trim() ||
      data.dob ||
      data.securityLicense.trim() ||
      data.governmentId.trim() ||
      data.file ||
      data.operationalRadius != null ||
      Object.values(data.availability).some(day => day.length > 0)
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

    // Contact
    if (!this.guardFormModel.contact.trim()) {
      this.guardErrors.contact = 'Contact Number is required.';
    } else if (!/^(\+1)?[ -]?\(?[2-9]\d{2}\)?[ -]?\d{3}[ -]?\d{4}$/.test(this.guardFormModel.contact)) {
      this.guardErrors.contact = 'Invalid phone number.';
    }

    // Security License
    if (!this.guardFormModel.securityLicense.trim()) {
      this.guardErrors.securityLicense = 'Security License is required.';
    } else if (!/^[A-Z0-9]{6,10}$/i.test(this.guardFormModel.securityLicense)) {
      this.guardErrors.securityLicense = 'Invalid Security License.';
    }

    // Government ID (digits → formatted)
    const rawGovId = this.guardFormModel.governmentId.replace(/-/g, '');
    if (!rawGovId) {
      this.guardErrors.governmentId = 'Government ID is required.';
    } else if (!/^\d{9}$/.test(rawGovId)) {
      this.guardErrors.governmentId = 'Government ID must be exactly 9 digits.';
    } else {
      this.guardFormModel.governmentId =
        rawGovId.replace(/(\d{3})(\d{3})(\d{3})/, '$1-$2-$3');
    }

    // Operational Radius
    if (
      this.guardFormModel.operationalRadius != null &&
      (isNaN(this.guardFormModel.operationalRadius) ||
        this.guardFormModel.operationalRadius < 1)
    ) {
      this.guardErrors.operationalRadius = 'Operational radius must be at least 1 mile.';
    }

    // Address
    if (!this.guardFormModel.address.trim()) {
      this.guardErrors.address = 'Home Address is required.';
    } else if (this.guardFormModel.address.trim().length < 10) {
      this.guardErrors.address = 'Address must be at least 10 characters long.';
    }

    return Object.keys(this.guardErrors).length === 0;
  }

  submitGuardForm(): void {
    if (!this.validateGuardForm()) {
      return;
    }

    if (this.guardData) {
      // Update dummy onboarding object
      Object.assign(
        this.guardData,
        JSON.parse(JSON.stringify(this.guardFormModel))
      );
      this.isEditMode = true;
      console.log('Guard data updated:', this.guardData);
    } else {
      console.log('New guard data submitted:', this.guardFormModel);
    }
  }
}