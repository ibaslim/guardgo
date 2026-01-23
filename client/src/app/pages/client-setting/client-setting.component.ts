import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { TextareaComponent } from '../../components/form/textarea/textarea.component';
import { FileUploadComponent } from '../../components/form/file-upload/file-upload.component';
import { ErrorMessageComponent } from "../../components/error-message/error-message.component";
import { Client } from '../onboarding/onboarding.component';

@Component({
  selector: 'app-client-setting',
  imports: [CommonModule,
    FormsModule,
    BaseInputComponent,
    TextareaComponent,
    FileUploadComponent, ErrorMessageComponent],
  templateUrl: './client-setting.component.html',
  styleUrl: './client-setting.component.css'
})
export class ClientSettingComponent {

  @Input() clientData?: Client;

  clientFormModel: Client = {
    legalEntityName: '',
    primaryContactInfo: '',
    billingAddress: '',
    businessLogo: null,
    sites: [
      { siteName: '', siteAddress: '' }
    ]
  };

  clientErrors: any = {};

  isEditMode: boolean = false;

  ngOnInit() {
    // Check if clientData has any real values
    if (this.clientData && this.hasClientData(this.clientData)) {
      this.clientFormModel = JSON.parse(JSON.stringify(this.clientData)); // deep copy
      this.isEditMode = true;
    } else {
      this.isEditMode = false; // fresh form
    }
  }

  // Helper function to check if object is empty
  hasClientData(data: Client): boolean {
    return !!(
      data.legalEntityName.trim() ||
      data.primaryContactInfo.trim() ||
      data.billingAddress.trim() ||
      (data.sites && data.sites.some(site => site.siteName.trim() || site.siteAddress.trim()))
    );
  }


  addSite() {
    this.clientFormModel.sites.push({ siteName: '', siteAddress: '' });
  };

  validateClientForm(): boolean {
    this.clientErrors = {};
    // Legal Entity Name validation
    if (!this.clientFormModel.legalEntityName || this.clientFormModel.legalEntityName.trim() === '') {
      this.clientErrors.legalEntityName = 'Legal Entity Name is required.';
    }
    // Business Contact Number validation
    if (!this.clientFormModel.primaryContactInfo || this.clientFormModel.primaryContactInfo.trim() === '') {
      this.clientErrors.primaryContactInfo = 'Business Contact Number is required.';
    } else if (!/^(\+1)?[ -]?\(?[2-9]\d{2}\)?[ -]?\d{3}[ -]?\d{4}$/.test(this.clientFormModel.primaryContactInfo)) {
      this.clientErrors.primaryContactInfo = 'Invalid phone number.';
    }
    // Billing Address validation
    if (!this.clientFormModel.billingAddress || this.clientFormModel.billingAddress.trim() === '') {
      this.clientErrors.billingAddress = 'Billing Address is required.';
    } else if (this.clientFormModel.billingAddress.trim().length < 10) {
      this.clientErrors.billingAddress = 'Billing Address must be at least 10 characters long.';
    }
    // Sites validation (ONLY first site required)
    if (!this.clientFormModel.sites || this.clientFormModel.sites.length === 0) {
      this.clientErrors.sites = 'At least one site is required.';
    } else {
      const firstSite = this.clientFormModel.sites[0];

      if (!firstSite.siteName || firstSite.siteName.trim() === '') {
        this.clientErrors.siteName0 = 'Site Name is required.';
      }

      if (!firstSite.siteAddress || firstSite.siteAddress.trim() === '') {
        this.clientErrors.siteAddress0 = 'Site Address is required.';
      }
    }

    return Object.keys(this.clientErrors).length === 0;
  };

  submitClientForm() {
    if (!this.validateClientForm()) {
      return;
    }
    if (this.clientData) {
      Object.assign(this.clientData, JSON.parse(JSON.stringify(this.clientFormModel)));
      this.isEditMode = true;
      console.log("Client data updated:", this.clientData);
    }
    else {
      console.log("New client data submitted:", this.clientFormModel);
    }
  }

};