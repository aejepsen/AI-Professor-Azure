// src/app/chat/chat.component.ts
import {
  Component, OnInit, OnDestroy, signal, computed,
  inject, ElementRef, ViewChild, AfterViewChecked
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { marked } from 'marked';
import { ChatService, ChatMessage, AnswerSource } from '../core/services/chat.service';
import { TeamsService } from '../core/services/teams.service';
import { TeamsAuthService } from '../core/auth/teams-auth.service';
import { SourcePanelComponent } from '../shared/source-panel/source-panel.component';
import { FeedbackComponent } from '../shared/feedback/feedback.component';

function uuid(): string {
  return crypto.randomUUID();
}

interface UiMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;           // markdown string, streamed progressively
  sources: AnswerSource[];
  timestamp: Date;
  streaming: boolean;
  error: boolean;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, SourcePanelComponent, FeedbackComponent],
  template: `
    <div class="chat-shell" [attr.data-theme]="teams.theme()">

      <!-- ── Message List ── -->
      <div class="messages-area" #messagesArea>
        <div *ngIf="messages().length === 0" class="empty-state">
          <div class="empty-icon">🎓</div>
          <h2>Como posso ajudar?</h2>
          <p>Pergunte sobre processos, políticas, encontre trechos de vídeos ou documentos.</p>
          <div class="suggestions">
            <button *ngFor="let s of suggestions" class="suggestion-chip" (click)="send(s)">
              {{ s }}
            </button>
          </div>
        </div>

        <div *ngFor="let msg of messages(); trackBy: trackById" class="message-row" [class]="msg.role">

          <!-- User message -->
          <div *ngIf="msg.role === 'user'" class="bubble user-bubble">
            <span class="avatar user-avatar">
              {{ userInitials() }}
            </span>
            <p class="message-text">{{ msg.content }}</p>
          </div>

          <!-- Assistant message -->
          <div *ngIf="msg.role === 'assistant'" class="bubble assistant-bubble">
            <span class="avatar bot-avatar">🎓</span>
            <div class="message-body">
              <div class="message-text markdown-body"
                   [innerHTML]="renderMarkdown(msg.content)">
              </div>

              <!-- Typing indicator while streaming -->
              <div *ngIf="msg.streaming" class="typing-indicator">
                <span></span><span></span><span></span>
              </div>

              <!-- Sources panel -->
              <app-source-panel
                *ngIf="!msg.streaming && msg.sources.length > 0"
                [sources]="msg.sources"
                (openVideo)="onOpenVideo($event)"
                (openDoc)="onOpenDoc($event)">
              </app-source-panel>

              <!-- Feedback -->
              <app-feedback
                *ngIf="!msg.streaming && !msg.error"
                [messageId]="msg.id"
                (feedback)="onFeedback($event)">
              </app-feedback>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Input Bar ── -->
      <div class="input-bar">
        <textarea
          #inputEl
          [(ngModel)]="question"
          (keydown.enter)="onEnter($event)"
          [disabled]="isStreaming()"
          placeholder="Digite sua pergunta... (Enter para enviar, Shift+Enter para nova linha)"
          rows="1"
          class="question-input"
          (input)="autoResize($event)">
        </textarea>
        <button
          class="send-btn"
          [disabled]="!question.trim() || isStreaming()"
          (click)="send(question)">
          <span *ngIf="!isStreaming()">➤</span>
          <span *ngIf="isStreaming()" class="spinner"></span>
        </button>
      </div>

    </div>
  `,
  styleUrls: ['./chat.component.scss'],
})
export class ChatComponent implements OnInit, AfterViewChecked, OnDestroy {
  @ViewChild('messagesArea') messagesArea!: ElementRef<HTMLDivElement>;
  @ViewChild('inputEl')      inputEl!: ElementRef<HTMLTextAreaElement>;

  private chatSvc  = inject(ChatService);
  readonly teams   = inject(TeamsService);
  private auth     = inject(TeamsAuthService);
  private destroy$ = new Subject<void>();

  messages    = signal<UiMessage[]>([]);
  isStreaming = signal(false);
  question    = '';
  conversationId = uuid();

  userInitials = computed(() => {
    const name = this.auth.profile()?.displayName ?? 'U';
    return name.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase();
  });

  suggestions = [
    'Como abrir um chamado de TI?',
    'Qual é a política de reembolso de despesas?',
    'Em que minuto do vídeo de onboarding falam sobre férias?',
    'Quais são os passos do processo de aprovação de compras?',
  ];

  private shouldScrollToBottom = false;

  ngOnInit() {}

  onEnter(event: KeyboardEvent) {
    if (!event.shiftKey) {
      event.preventDefault();
      this.send(this.question);
    }
  }

  send(text: string) {
    const q = text.trim();
    if (!q || this.isStreaming()) return;
    this.question = '';

    const userMsg: UiMessage = {
      id: uuid(), role: 'user', content: q,
      sources: [], timestamp: new Date(),
      streaming: false, error: false,
    };
    const botMsg: UiMessage = {
      id: uuid(), role: 'assistant', content: '',
      sources: [], timestamp: new Date(),
      streaming: true, error: false,
    };

    this.messages.update(m => [...m, userMsg, botMsg]);
    this.isStreaming.set(true);
    this.shouldScrollToBottom = true;

    this.chatSvc
      .streamAnswer(q, this.conversationId, this.toHistory())
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: chunk => {
          if (chunk.type === 'token') {
            this.messages.update(msgs =>
              msgs.map(m => m.id === botMsg.id
                ? { ...m, content: m.content + (chunk.text ?? '') }
                : m
              )
            );
            this.shouldScrollToBottom = true;
          }
          if (chunk.type === 'sources') {
            this.messages.update(msgs =>
              msgs.map(m => m.id === botMsg.id
                ? { ...m, sources: chunk.sources ?? [] }
                : m
              )
            );
          }
          if (chunk.type === 'error') {
            this.messages.update(msgs =>
              msgs.map(m => m.id === botMsg.id
                ? { ...m, content: chunk.error ?? 'Erro ao processar resposta.', streaming: false, error: true }
                : m
              )
            );
            this.isStreaming.set(false);
          }
        },
        complete: () => {
          this.messages.update(msgs =>
            msgs.map(m => m.id === botMsg.id ? { ...m, streaming: false } : m)
          );
          this.isStreaming.set(false);
        },
      });
  }

  renderMarkdown(content: string): string {
    return marked(content) as string;
  }

  onOpenVideo(source: AnswerSource) {
    this.teams.openVideoAtTimestamp(source.url, source.timestamp_start ?? 0);
  }

  onOpenDoc(source: AnswerSource) {
    this.teams.openFileDeepLink(source.url, source.name);
  }

  onFeedback(event: { messageId: string; positive: boolean }) {
    this.chatSvc.submitFeedback(event.messageId, event.positive)
      .pipe(takeUntil(this.destroy$))
      .subscribe();
  }

  trackById = (_: number, msg: UiMessage) => msg.id;

  autoResize(event: Event) {
    const el = event.target as HTMLTextAreaElement;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }

  ngAfterViewChecked() {
    if (this.shouldScrollToBottom) {
      const el = this.messagesArea?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
      this.shouldScrollToBottom = false;
    }
  }

  private toHistory(): ChatMessage[] {
    return this.messages().map(m => ({
      id: m.id, role: m.role, content: m.content,
      sources: m.sources, timestamp: m.timestamp,
    }));
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
