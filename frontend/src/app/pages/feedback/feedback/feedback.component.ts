import { Component, EventEmitter, Output } from '@angular/core';
import {
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  Validators
} from '@angular/forms';

import { FeedbackService } from '../../../core/services/feedback.service';

@Component({
  selector: 'app-feedback-form',
  standalone: true,
  imports: [
    ReactiveFormsModule
  ],
  templateUrl: './feedback-form.component.html',
  styleUrl: './feedback-form.component.scss'
})
export class FeedbackFormComponent {

  @Output()
  submitted = new EventEmitter<void>();

  feedbackForm: FormGroup;

  isSubmitting = false;
  submitError = '';
  submitSuccess = false;

  constructor(
    private readonly fb: FormBuilder,
    private readonly feedbackService: FeedbackService
  ) {

    this.feedbackForm = this.fb.group({

      type: [
        '',
        Validators.required
      ],

      subject: [
        '',
        [
          Validators.required,
          Validators.minLength(5),
          Validators.maxLength(150)
        ]
      ],

      description: [
        '',
        [
          Validators.required,
          Validators.minLength(10),
          Validators.maxLength(2000)
        ]
      ]
    });
  }

  submit(): void {

    if (this.feedbackForm.invalid) {

      this.feedbackForm.markAllAsTouched();

      return;
    }

    this.isSubmitting = true;
    this.submitError = '';
    this.submitSuccess = false;

    const payload = this.feedbackForm.getRawValue();

    this.feedbackService
      .submitFeedback(payload)
      .subscribe({

        next: () => {

          this.isSubmitting = false;
          this.submitSuccess = true;

          this.feedbackForm.reset();

          this.submitted.emit();
        },

        error: () => {

          this.isSubmitting = false;

          this.submitError =
            'Unable to submit feedback. Please try again.';
        }
      });
  }
}