import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BaseInputComponent } from '../form/base-input/base-input.component';
import { SelectInputComponent } from '../form/select-input/select-input.component';
import { ErrorMessageComponent } from '../error-message/error-message.component';
import { ButtonComponent } from '../button/button.component';
import { CardComponent } from '../card/card.component';
import { SectionComponent } from '../section/section.component';

interface Address {
  street: string;
  city: string;
  country: string;
  province: string;
  postalCode: string;
}

interface Site {
  siteName: string;
  siteAddress: Address;
  siteManagerContact: string;
  managerEmail: string;
  numberOfGuardsRequired: number | null;
  siteType: string;
}

@Component({
  selector: 'app-client-sites',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    BaseInputComponent,
    SelectInputComponent,
    ErrorMessageComponent,
    ButtonComponent,
    CardComponent,
    SectionComponent
  ],
  templateUrl: './client-sites.component.html'
})
export class ClientSitesComponent {
  @Input() sites: Site[] = [];
  @Input() errors: Record<string, string> = {};
  @Input() countryOptions: { value: string; label: string }[] = [];
  @Input() provinceOptions: { value: string; label: string }[] = [];
  @Input() siteTypeOptions: { value: string; label: string }[] = [];
  @Input() title = 'Sites';
  @Input() subtitle = 'Add locations we will service.';
  @Input() requiredFirst = true;

  @Output() addSite = new EventEmitter<void>();
  @Output() removeSite = new EventEmitter<number>();

  onAddSite(): void {
    this.addSite.emit();
  }

  onRemoveSite(index: number): void {
    this.removeSite.emit(index);
  }
}
