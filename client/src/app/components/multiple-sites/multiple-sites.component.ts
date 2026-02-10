import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { ErrorMessageComponent } from '../error-message/error-message.component';
import { BaseInputComponent } from '../form/base-input/base-input.component';
import { FormsModule } from '@angular/forms';

export interface Address {
  street: string;
  city: string;
  country: string;
  postalCode: string;
}

export interface Site {
  siteName: string;
  siteAddress: Address;
}

@Component({
  selector: 'app-multiple-sites',
  imports: [CommonModule, FormsModule, BaseInputComponent, ErrorMessageComponent],
  templateUrl: './multiple-sites.component.html',
  styleUrl: './multiple-sites.component.css'
})
export class MultipleSitesComponent {
  @Input() sites: Site[] = [
    {
      siteName: '',
      siteAddress: {
        street: '',
        city: '',
        country: '',
        postalCode: ''
      }
    }
  ]

  @Output() sitesChange = new EventEmitter<Site[]>();
  @Output() validateChange = new EventEmitter<boolean>();

  siteError: any = {};

  addSite() {
    this.sites.push({
      siteName: '',
      siteAddress: {
        street: '',
        city: '',
        country: '',
        postalCode: ''
      }
    });
    this.emitChanges();
  }

  removeSite(index: number) {
    if (this.sites.length > 1 && index !== 0) {
      this.sites.splice(index, 1);
      this.emitChanges();
    }
  }

  onSiteChange() {
    this.emitChanges();
  }

  private emitChanges() {
    this.sitesChange.emit(this.sites);
    this.validateSites();
  }

  validateSites(): boolean {
    this.siteError = {};

    if (!this.sites || this.sites.length === 0) {
      this.siteError.site = 'At least one site is required.';
    } else {
      const firstSite = this.sites[0];
      if (!firstSite.siteName || firstSite.siteName.trim() === '') {
        this.siteError.siteName0 = 'Site name is required.';
      }
      if (!firstSite.siteAddress.street.trim()) {
        this.siteError.street0 = 'Street is required.';
      }
      if (!firstSite.siteAddress.city.trim()) {
        this.siteError.city0 = 'City is required.';
      }
      if (!firstSite.siteAddress.country.trim()) {
        this.siteError.country0 = 'Country is required.';
      }
      if (!firstSite.siteAddress.postalCode.trim()) {
        this.siteError.postalCode0 = 'Postal code is required.';
      }
    }

    const isValid = Object.keys(this.siteError).length === 0;
    this.validateChange.emit(isValid);
    return isValid;
  }

  validate(): boolean {
    return this.validateSites();
  }

  getSites(): Site[] {
    return this.sites;
  }


}
