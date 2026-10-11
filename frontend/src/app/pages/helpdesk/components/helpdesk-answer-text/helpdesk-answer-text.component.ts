import { Component, Input } from '@angular/core';
import { AnswerSegment } from '../../answer-format';

/**
 * Renders one run of inline answer text.
 *
 * The segments are bound with interpolation, so the answer is always treated
 * as text — bold and italic runs become `<strong>`/`<em>` and nothing else is
 * interpreted.
 */
@Component({
  selector: 'app-helpdesk-answer-text',
  standalone: true,
  template: `
    @for (segment of segments; track $index) {
      @if (segment.bold) {
        <strong>{{ segment.text }}</strong>
      } @else if (segment.italic) {
        <em>{{ segment.text }}</em>
      } @else {
        <span>{{ segment.text }}</span>
      }
    }
  `,
})
export class HelpdeskAnswerTextComponent {
  @Input({ required: true }) segments: AnswerSegment[] = [];
}
