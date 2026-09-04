import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';

@Component({
  selector: 'app-password-meter',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './password-meter.component.html',
  styleUrl: './password-meter.component.css'
})
export class PasswordMeterComponent implements OnChanges {
  @Input() password = '';

  score = 0;
  label = '';
  levelClass = '';

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['password']) {
      this.calculateStrength(this.password || '');
    }
  }

  calculateStrength(pwd: string): void {
    if (!pwd) {
      this.score = 0;
      this.label = '';
      this.levelClass = '';
      return;
    }

    let calculated = 0;

    // Rule 1: Minimum 8 characters
    if (pwd.length >= 8) {
      calculated++;
    }

    // Rule 2: Upper and lowercase letters
    if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) {
      calculated++;
    }

    // Rule 3: Digits
    if (/\d/.test(pwd)) {
      calculated++;
    }

    // Rule 4: Special characters
    if (/[!@#$%^&*(),.?":{}|<>]/.test(pwd)) {
      calculated++;
    }

    this.score = calculated;

    switch (this.score) {
      case 1:
        this.label = 'Weak';
        this.levelClass = 'level-weak';
        break;
      case 2:
        this.label = 'Medium';
        this.levelClass = 'level-medium';
        break;
      case 3:
        this.label = 'Strong';
        this.levelClass = 'level-strong';
        break;
      case 4:
        this.label = 'Secure';
        this.levelClass = 'level-secure';
        break;
      default:
        this.label = 'Very Weak';
        this.levelClass = 'level-weak';
    }
  }
}
