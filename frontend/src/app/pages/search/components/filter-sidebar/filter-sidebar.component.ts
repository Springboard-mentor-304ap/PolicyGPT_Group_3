import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SearchFilters, SearchItemType } from '../../../../core/models/search.models';
import { SelectComponent, SelectOption } from '../../../../shared/components/select/select.component';

@Component({
  selector: 'app-filter-sidebar',
  standalone: true,
  imports: [CommonModule, FormsModule, SelectComponent],
  templateUrl: './filter-sidebar.component.html',
  styleUrl: './filter-sidebar.component.css',
})
export class FilterSidebarComponent {
  @Input() filters: SearchFilters = {
    type: 'all',
    category: 'all',
    state: 'all',
    department: '',
  };

  @Output() filtersChange = new EventEmitter<SearchFilters>();
  @Output() reset = new EventEmitter<void>();

  typeOptions: { value: SearchItemType; label: string }[] = [
    { value: 'all', label: 'All Resources' },
    { value: 'scheme', label: 'Welfare Schemes' },
    { value: 'policy', label: 'National Policies' },
  ];

  categoryOptions: SelectOption[] = [
    { value: 'all', label: 'All Categories' },
    { value: 'farmer_welfare', label: 'Farmer Welfare & Agriculture' },
    { value: 'scholarships', label: 'Scholarships & Students' },
    { value: 'healthcare', label: 'Healthcare & Medical Cover' },
    { value: 'housing', label: 'Housing & Urban Development' },
    { value: 'women_empowerment', label: 'Women & Child Welfare' },
    { value: 'employment_programs', label: 'Employment & Skilling' },
    { value: 'social_security', label: 'Social Security & Pensions' },
    { value: 'education', label: 'Education Policy' },
    { value: 'digital_governance', label: 'Digital Governance & IT' },
    { value: 'environment', label: 'Environment & Green Energy' },
  ];

  stateOptions: SelectOption[] = [
    { value: 'all', label: 'All India (Central & States)' },
    { value: 'Central', label: 'Central Government' },
    { value: 'Maharashtra', label: 'Maharashtra' },
    { value: 'Karnataka', label: 'Karnataka' },
    { value: 'Uttar Pradesh', label: 'Uttar Pradesh' },
    { value: 'Tamil Nadu', label: 'Tamil Nadu' },
    { value: 'Delhi', label: 'Delhi (NCT)' },
    { value: 'Gujarat', label: 'Gujarat' },
    { value: 'Rajasthan', label: 'Rajasthan' },
  ];

  onTypeSelect(type: SearchItemType): void {
    this.filters.type = type;
    this.emitChange();
  }

  onCategorySelect(category: string): void {
    this.filters.category = category;
    this.emitChange();
  }

  onStateSelect(state: string): void {
    this.filters.state = state;
    this.emitChange();
  }

  onReset(): void {
    this.filters = {
      type: 'all',
      category: 'all',
      state: 'all',
      department: '',
    };
    this.reset.emit();
    this.emitChange();
  }

  get activeFiltersCount(): number {
    let count = 0;
    if (this.filters.type !== 'all') count++;
    if (this.filters.category !== 'all') count++;
    if (this.filters.state !== 'all') count++;
    return count;
  }

  private emitChange(): void {
    this.filtersChange.emit({ ...this.filters });
  }
}
