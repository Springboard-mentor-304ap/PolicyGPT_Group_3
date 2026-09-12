import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-scheme-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './scheme-list.html',
  styleUrl: './scheme-list.css'
})
export class SchemeList {

  schemes = [
    {
      id: 1,
      title: 'Student Scholarship Scheme',
      category: 'scholarships',
      department: 'Education Department',
      state: 'Andhra Pradesh',
      status: 'active'
    },
    {
      id: 2,
      title: 'Farmer Welfare Scheme',
      category: 'farmer-welfare',
      department: 'Agriculture Department',
      state: 'Andhra Pradesh',
      status: 'draft'
    },
    {
      id: 3,
      title: 'Women Empowerment Scheme',
      category: 'women_empowerment',
      department: 'Women and Child Welfare Department',
      state: 'Andhra Pradesh',
      status: 'archived'
    }
  ];

}