// src/app/core/services/chat.service.ts
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface ChatMessage {
  id:        string;
  role:      'user' | 'assistant';
  content:   string;
  sources?:  Source[];
  timestamp: string;
  loading?:  boolean;
  error?:    string;
}

export interface Source {
  id:               string;
  type:             string;
  name:             string;
  url:              string;
  page?:            number;
  timestamp_start?: number;
  timestamp_end?:   number;
  relevance_score:  number;
}

export interface ChatRequest {
  question:        string;
  conversation_id: string;
  history:         { role: string; content: string }[];
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private http = inject(HttpClient);
  private base = environment.apiUrl;

  streamAnswer(
    question: string,
    conversationId: string,
    history: { role: string; content: string }[] = [],
  ): Observable<any> {
    return new Observable(subscriber => {
      const url = `${this.base}/chat/stream`;
      const body: ChatRequest = { question, conversation_id: conversationId, history };

      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(async response => {
        if (!response.ok || !response.body) {
          subscriber.error(new Error(`HTTP ${response.status}`));
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const chunk = JSON.parse(line.slice(6));
                subscriber.next(chunk);
                if (chunk.type === 'done' || chunk.type === 'error') {
                  subscriber.complete();
                  return;
                }
              } catch (_) {}
            }
          }
        }
        subscriber.complete();
      }).catch(err => subscriber.error(err));
    });
  }

  submitFeedback(messageId: string, positive: boolean, comment?: string) {
    return this.http.post(`${this.base}/chat/feedback`, {
      message_id: messageId,
      positive,
      comment,
    });
  }
}
