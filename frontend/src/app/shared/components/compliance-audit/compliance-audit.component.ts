import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';

export interface AuditRule {
  id: string;
  label: string;
  passed: boolean;
}

@Component({
  selector: 'app-compliance-audit',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './compliance-audit.component.html',
  styleUrl: './compliance-audit.component.css'
})
export class ComplianceAuditComponent implements OnChanges {
  @Input() password = '';

  rules: AuditRule[] = [
    { id: 'min-length', label: 'At least 8 characters long', passed: false },
    { id: 'case', label: 'Must include upper & lowercase', passed: false },
    { id: 'digits', label: 'Contains numerical digits (0-9)', passed: false },
    { id: 'special', label: 'Special character (!@#$%)', passed: false }
  ];

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['password']) {
      this.evaluateCompliance(this.password || '');
    }
  }

  evaluateCompliance(pwd: string): void {
    this.rules = [
      {
        id: 'min-length',
        label: 'At least 8 characters long',
        passed: pwd.length >= 8
      },
      {
        id: 'case',
        label: 'Must include upper & lowercase',
        passed: /[a-z]/.test(pwd) && /[A-Z]/.test(pwd)
      },
      {
        id: 'digits',
        label: 'Contains numerical digits (0-9)',
        passed: /\d/.test(pwd)
      },
      {
        id: 'special',
        label: pwd && !/[!@#$%^&*(),.?":{}|<>]/.test(pwd)
          ? 'Special character (!@#$%) missing'
          : 'Special character (!@#$%)',
        passed: /[!@#$%^&*(),.?":{}|<>]/.test(pwd)
      }
    ];
  }
}
