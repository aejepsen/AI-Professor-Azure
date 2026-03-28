// src/app/core/services/chat.service.ts
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, Subject } from 'rxjs';
import { environment } from '../../../environments/environment';
import { TeamsAuthService } from '../auth/teams-auth.service';

export interface StreamChunk {
  type: 'token' | 'sources' | 'done' | 'error';
  text?: string;
  sources?: AnswerSource[];
  error?: string;
}

export interface AnswerSource {
  id: string;
  type: 'video' | 'document' | 'policy';
  name: string;
  url: string;
  page?: number;
  timestamp_start?: number;   // seconds
  timestamp_end?: number;
  sensitivity_label: string;
  relevance_score: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: AnswerSource[];
  timestamp: Date;
  ragas_score?: number;
}

export interface ConversationHistory {
  id: string;
  title: string;
  messages: ChatMessage[];
  created_at: Date;
  updated_at: Date;
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private auth = inject(TeamsAuthService);
  private http = inject(HttpClient);

  /**
   * Streams the answer from Claude via SSE.
   * Each emission is a StreamChunk — token, sources, or done.
   */
  streamAnswer(
    question: string,
    conversationId: string,
    history: ChatMessage[]
  ): Observable<StreamChunk> {
    const subject = new Subject<StreamChunk>();
    const token   = this.auth.token();

    const eventSource = new EventSourcePolyfill(
      `${environment.apiUrl}/chat/stream`,
      {
        headers: { Authorization: `Bearer ${token}` },
        // EventSource does not support POST natively — use polyfill
        method: 'POST',
        body: JSON.stringify({
          question,
          conversation_id: conversationId,
          history: history.slice(-10).map(m => ({ role: m.role, content: m.content })),
        }),
      }
    );

    eventSource.onmessage = (event: MessageEvent) => {
      const chunk: StreamChunk = JSON.parse(event.data);
      subject.next(chunk);
      if (chunk.type === 'done' || chunk.type === 'error') {
        eventSource.close();
        subject.complete();
      }
    };

    eventSource.onerror = () => {
      subject.next({ type: 'error', error: 'Conexão interrompida. Tente novamente.' });
      eventSource.close();
      subject.complete();
    };

    return subject.asObservable();
  }

  /** Submit thumbs down feedback — triggers RAGAS re-evaluation */
  submitFeedback(messageId: string, positive: boolean, comment?: string): Observable<void> {
    return this.http.post<void>(`${environment.apiUrl}/chat/feedback`, {
      message_id: messageId,
      positive,
      comment,
    });
  }

  /** Load conversation history (paginated) */
  getHistory(page = 0, size = 20): Observable<ConversationHistory[]> {
    return this.http.get<ConversationHistory[]>(
      `${environment.apiUrl}/conversations?page=${page}&size=${size}`
    );
  }

  /** Load a specific conversation */
  getConversation(id: string): Observable<ConversationHistory> {
    return this.http.get<ConversationHistory>(`${environment.apiUrl}/conversations/${id}`);
  }
}

// Minimal EventSource polyfill type reference
// Install: npm install event-source-polyfill
declare class EventSourcePolyfill {
  constructor(url: string, options: any);
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: (() => void) | null;
  close(): void;
}
