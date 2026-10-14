import {
  Component,
  OnInit
} from '@angular/core';

import { FeedbackService } from '../../../core/services/feedback.service';
import { Feedback } from '../../../core/models/feedback.model';
import { DatePipe } from '@angular/common';

@Component({
  selector: 'app-my-feedback',
  standalone: true,

  imports: [
    DatePipe
  ],

  templateUrl: './my-feedback.component.html',
  styleUrl: './my-feedback.component.scss'
})
export class MyFeedbackComponent implements OnInit {

  feedbackList: Feedback[] = [];

  isLoading = true;

  loadError = '';

  constructor(
    private readonly feedbackService: FeedbackService
  ) {}

  ngOnInit(): void {

    this.loadMyFeedback();
  }

  loadMyFeedback(): void {

    this.isLoading = true;
    this.loadError = '';

    this.feedbackService
      .getMyFeedback()
      .subscribe({

        next: (feedback) => {

          this.feedbackList = feedback;

          this.isLoading = false;
        },

        error: () => {

          this.isLoading = false;

          this.loadError =
            'Unable to load your feedback. Please try again.';
        }
      });
  }

  retry(): void {

    this.loadMyFeedback();
  }
}