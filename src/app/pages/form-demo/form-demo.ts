import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BaseDropdown, DropdownOption } from '../../partials/base-dropdown/base-dropdown';
import {
  BaseMultiSelect,
  MultiSelectOption,
} from '../../partials/base-multi-select/base-multi-select';

@Component({
  selector: 'app-form-demo',
  imports: [CommonModule, FormsModule, BaseDropdown, BaseMultiSelect],
  templateUrl: './form-demo.html',
  styleUrl: './form-demo.css',
})
export class FormDemo {
  darkMode = false;

  // Single Dropdown Examples
  countryOptions: DropdownOption[] = [
    { label: 'United States', value: 'us' },
    { label: 'United Kingdom', value: 'uk' },
    { label: 'Canada', value: 'ca' },
    { label: 'Australia', value: 'au' },
    { label: 'Germany', value: 'de' },
    { label: 'France', value: 'fr' },
    { label: 'Japan', value: 'jp' },
    { label: 'China', value: 'cn' },
    { label: 'India', value: 'in' },
    { label: 'Brazil', value: 'br' },
  ];

  priorityOptions: DropdownOption[] = [
    { label: 'Low', value: 'low' },
    { label: 'Medium', value: 'medium' },
    { label: 'High', value: 'high' },
    { label: 'Critical', value: 'critical' },
  ];

  statusOptions: DropdownOption[] = [
    { label: 'Active', value: 'active' },
    { label: 'Inactive', value: 'inactive' },
    { label: 'Pending', value: 'pending' },
    { label: 'Disabled', value: 'disabled', disabled: true },
  ];

  // Multi-Select Examples
  skillsOptions: MultiSelectOption[] = [
    { label: 'JavaScript', value: 'js' },
    { label: 'TypeScript', value: 'ts' },
    { label: 'Python', value: 'python' },
    { label: 'Java', value: 'java' },
    { label: 'C++', value: 'cpp' },
    { label: 'Go', value: 'go' },
    { label: 'Rust', value: 'rust' },
    { label: 'Ruby', value: 'ruby' },
    { label: 'PHP', value: 'php' },
    { label: 'Swift', value: 'swift' },
  ];

  interestsOptions: MultiSelectOption[] = [
    { label: 'Web Development', value: 'web' },
    { label: 'Mobile Development', value: 'mobile' },
    { label: 'Machine Learning', value: 'ml' },
    { label: 'DevOps', value: 'devops' },
    { label: 'Cloud Computing', value: 'cloud' },
    { label: 'Cybersecurity', value: 'security' },
    { label: 'Data Science', value: 'data' },
    { label: 'UI/UX Design', value: 'design' },
  ];

  tagsOptions: MultiSelectOption[] = [
    { label: 'Important', value: 'important' },
    { label: 'Urgent', value: 'urgent' },
    { label: 'Review', value: 'review' },
    { label: 'Follow-up', value: 'followup' },
    { label: 'Bug', value: 'bug' },
    { label: 'Feature', value: 'feature' },
    { label: 'Documentation', value: 'docs' },
    { label: 'Test', value: 'test' },
  ];

  // Form Values
  selectedCountry: string = '';
  selectedPriority: string = '';
  selectedStatus: string = 'active';
  selectedSkills: string[] = [];
  selectedInterests: string[] = ['web', 'mobile'];
  selectedTags: string[] = [];

  constructor() {
    // Load theme preference from localStorage
    const savedTheme = localStorage.getItem('theme');
    this.darkMode = savedTheme === 'dark';

    // Apply the correct theme
    if (this.darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }

  toggleDarkMode() {
    this.darkMode = !this.darkMode;
    if (this.darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }

  onCountryChange(value: any) {
    console.log('Country changed:', value);
  }

  onPriorityChange(value: any) {
    console.log('Priority changed:', value);
  }

  onStatusChange(value: any) {
    console.log('Status changed:', value);
  }

  onSkillsChange(values: any[]) {
    console.log('Skills changed:', values);
  }

  onInterestsChange(values: any[]) {
    console.log('Interests changed:', values);
  }

  onTagsChange(values: any[]) {
    console.log('Tags changed:', values);
  }

  submitForm() {
    console.log('Form submitted:', {
      country: this.selectedCountry,
      priority: this.selectedPriority,
      status: this.selectedStatus,
      skills: this.selectedSkills,
      interests: this.selectedInterests,
      tags: this.selectedTags,
    });

    alert('Form submitted! Check the console for details.');
  }
}
