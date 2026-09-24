import {
  Component
} from '@angular/core';

import { FeedbackFormComponent } from '../feedback/feedback.component';
import { MyFeedbackComponent } from '../my-feedback/my-feedback.component';

@Component({
  selector: 'app-feedback-page',
  standalone: true,
  imports: [
    FeedbackFormComponent,
    MyFeedbackComponent
  ],
  templateUrl: './feedback-page.component.html',
  styleUrl: './feedback-page.component.scss'
})
export class FeedbackPageComponent {

  myFeedbackComponent?: MyFeedbackComponent;

  refreshMyFeedback(): void {

    this.myFeedbackComponent?.loadMyFeedback();
  }
}