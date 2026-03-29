// src/app/core/services/chat.service.ts
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { MsalService } from '@azure/msal-angular';
import { environment } from '../../../environments/environment';

export interface Source {
  id: string;
  type: string;
  name: string;
  url: string;
  page?: number;
  timestamp_start?: number;
  timestamp_end?: number;
  relevance_score: number;
  sensitivity_label?: string;
}

export type AnswerSource = Source;

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: string;
  loading?: boolean;
  error?: string;
}

export interface ConversationHistory {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private http = inject(HttpClient);
  private msal = inject(MsalService);
  private base = environment.apiUrl;

  private async getToken(): Promise<string> {
    const account = this.msal.instance.getActiveAccount()
      || this.msal.instance.getAllAccounts()[0];
    if (!account) return '';
    try {
      const result = await this.msal.instance.acquireTokenSilent({
        scopes: [environment.apiScope || 'User.Read'],
        account,
      });
      return result.accessToken;
    } catch (_) {
      return '';
    }
  }

  streamAnswer(
    question: string,
    conversationId: string,
    history: { role: string; content: string }[] = [],
  ): Observable<any> {
    return new Observable(subscriber => {
      this.getToken().then(token => {
        fetch(`${this.base}/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ question, conversation_id: conversationId, history }),
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
    });
  }

  submitFeedback(messageId: string, positive: boolean, comment?: string) {
    return this.http.post(`${this.base}/chat/feedback`, {
      message_id: messageId, positive, comment,
    });
  }

  getHistory(page = 0, size = 20): Observable<ConversationHistory[]> {
    return this.http.get<ConversationHistory[]>(
      `${this.base}/conversations?page=${page}&size=${size}`
    );
  }

  getConversation(id: string): Observable<ConversationHistory> {
    return this.http.get<ConversationHistory>(`${this.base}/conversations/${id}`);
  }
}
