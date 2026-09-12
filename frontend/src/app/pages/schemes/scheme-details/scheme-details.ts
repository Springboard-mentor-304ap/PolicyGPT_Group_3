import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-scheme-details',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './scheme-details.html',
  styleUrl: './scheme-details.css'
})
export class SchemeDetails {

  scheme = {
    id: 1,
    policy_id: 'POL-001',
    title: 'Student Scholarship Scheme',
    description: 'Financial assistance for eligible students.',
    category: 'scholarships',
    benefits: 'Provides financial support to eligible students.',
    application_process: 'Apply through the official government portal.',
    department: 'Education Department',
    state: 'Andhra Pradesh',
    status: 'active',
    launch_date: '2026-06-01',
    deadline_date: '2026-12-31',
    document_url: 'https://example.gov.in/document'
  };

}