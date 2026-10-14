import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  Feedback,
  CreateFeedbackRequest
} from '../models/feedback.model';

@Injectable({
  providedIn: 'root'
})
export class FeedbackService {

  private readonly apiUrl = '/api/feedback';

  constructor(
    private readonly http: HttpClient
  ) {}

  submitFeedback(
    payload: CreateFeedbackRequest
  ): Observable<Feedback> {

    return this.http.post<Feedback>(
      this.apiUrl,
      payload
    );
  }

  getMyFeedback(): Observable<Feedback[]> {

    return this.http.get<Feedback[]>(
      `${this.apiUrl}/my`
    );
  }

  getFeedbackById(
    id: string
  ): Observable<Feedback> {

    return this.http.get<Feedback>(
      `${this.apiUrl}/${id}`
    );
  }
}