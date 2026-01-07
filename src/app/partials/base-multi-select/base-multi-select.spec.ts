import { ComponentFixture, TestBed } from '@angular/core/testing';
import { BaseMultiSelect } from './base-multi-select';

describe('BaseMultiSelect', () => {
  let component: BaseMultiSelect;
  let fixture: ComponentFixture<BaseMultiSelect>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BaseMultiSelect],
    }).compileComponents();

    fixture = TestBed.createComponent(BaseMultiSelect);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display placeholder when no options selected', () => {
    component.placeholder = 'Select options';
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Select options');
  });

  it('should toggle dropdown on click', () => {
    expect(component.isOpen).toBe(false);
    component.toggleDropdown();
    expect(component.isOpen).toBe(true);
    component.toggleDropdown();
    expect(component.isOpen).toBe(false);
  });

  it('should toggle option selection', () => {
    const option = { label: 'Test', value: 'test' };
    component.options = [option];
    
    component.toggleOption(option);
    expect(component.selectedValues).toContain('test');
    
    component.toggleOption(option);
    expect(component.selectedValues).not.toContain('test');
  });

  it('should select all options', () => {
    component.options = [
      { label: 'Option 1', value: '1' },
      { label: 'Option 2', value: '2' },
      { label: 'Option 3', value: '3' },
    ];
    component.selectAll();
    expect(component.selectedValues.length).toBe(3);
  });

  it('should clear all selections', () => {
    component.selectedValues = ['1', '2', '3'];
    component.clearAll();
    expect(component.selectedValues.length).toBe(0);
  });

  it('should filter options based on search term', () => {
    component.options = [
      { label: 'JavaScript', value: 'js' },
      { label: 'TypeScript', value: 'ts' },
      { label: 'Python', value: 'py' },
    ];
    component.searchTerm = 'script';
    expect(component.filteredOptions.length).toBe(2);
  });

  it('should display chips for selected options', () => {
    component.options = [
      { label: 'Option 1', value: '1' },
      { label: 'Option 2', value: '2' },
    ];
    component.selectedValues = ['1', '2'];
    expect(component.selectedOptions.length).toBe(2);
  });

  it('should show remaining count when max chips exceeded', () => {
    component.options = [
      { label: 'Option 1', value: '1' },
      { label: 'Option 2', value: '2' },
      { label: 'Option 3', value: '3' },
      { label: 'Option 4', value: '4' },
    ];
    component.selectedValues = ['1', '2', '3', '4'];
    component.maxDisplayChips = 2;
    expect(component.remainingCount).toBe(2);
  });

  it('should not toggle disabled option', () => {
    const option = { label: 'Test', value: 'test', disabled: true };
    component.options = [option];
    component.toggleOption(option);
    expect(component.selectedValues).not.toContain('test');
  });
});
