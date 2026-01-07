import { ComponentFixture, TestBed } from '@angular/core/testing';
import { BaseDropdown } from './base-dropdown';

describe('BaseDropdown', () => {
  let component: BaseDropdown;
  let fixture: ComponentFixture<BaseDropdown>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BaseDropdown],
    }).compileComponents();

    fixture = TestBed.createComponent(BaseDropdown);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display placeholder when no option is selected', () => {
    component.placeholder = 'Select option';
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Select option');
  });

  it('should toggle dropdown on click', () => {
    expect(component.isOpen).toBe(false);
    component.toggleDropdown();
    expect(component.isOpen).toBe(true);
    component.toggleDropdown();
    expect(component.isOpen).toBe(false);
  });

  it('should select an option', () => {
    const option = { label: 'Test', value: 'test' };
    component.options = [option];
    component.selectOption(option);
    expect(component.selectedOption).toEqual(option);
    expect(component.isOpen).toBe(false);
  });

  it('should filter options when searchable', () => {
    component.searchable = true;
    component.options = [
      { label: 'Apple', value: 'apple' },
      { label: 'Banana', value: 'banana' },
      { label: 'Cherry', value: 'cherry' },
    ];
    component.searchTerm = 'an';
    expect(component.filteredOptions.length).toBe(1);
    expect(component.filteredOptions[0].label).toBe('Banana');
  });

  it('should not select disabled option', () => {
    const option = { label: 'Test', value: 'test', disabled: true };
    component.options = [option];
    const initialSelection = component.selectedOption;
    component.selectOption(option);
    expect(component.selectedOption).toEqual(initialSelection);
  });
});
