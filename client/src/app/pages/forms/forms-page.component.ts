import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { MultiselectInputComponent } from '../../components/form/multiselect-input/multiselect-input.component';
import { TextareaComponent } from '../../components/form/textarea/textarea.component';
import { RadioComponent } from '../../components/form/radio/radio.component';
import { SwitchComponent } from '../../components/form/switch/switch.component';
import { FileUploadComponent } from '../../components/form/file-upload/file-upload.component';
import { WeeklyAvailabilityComponent } from "../../components/form/weekly-availability/weekly-availability.component";

@Component({
  selector: 'app-forms-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    BaseInputComponent,
    SelectInputComponent,
    MultiselectInputComponent,
    TextareaComponent,
    RadioComponent,
    SwitchComponent,
    FileUploadComponent,
    WeeklyAvailabilityComponent
],
  templateUrl: './forms-page.component.html',
  styleUrls: ['./forms-page.component.scss']
})
export class FormsPageComponent {
  formModel = {
    name: '',
    email: '',
    password: '',
    age: null,
    gender: '',
    country: '',
    skills: [],
    bio: '',
    notifications: false,
    terms: false,
    file: null,
    availability: {}
  };

  countries = [
    { label: 'United States', value: 'us' },
    { label: 'Canada', value: 'ca' },
    { label: 'United Kingdom', value: 'uk' },
    { label: 'Australia', value: 'au' }
  ];

  skills = [
    { label: 'Angular', value: 'angular' },
    { label: 'React', value: 'react' },
    { label: 'Vue', value: 'vue' },
    { label: 'Svelte', value: 'svelte' }
  ];

  genders = [
    { label: 'Male', value: 'male' },
    { label: 'Female', value: 'female' },
    { label: 'Other', value: 'other' }
  ];

  submit() {
    // For demo, just log the model
    alert(JSON.stringify(this.formModel, null, 2));
  }
}
