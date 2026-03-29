// src/app/chat/chat.component.ts
import { Component, inject, signal, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Store } from '@ngrx/store';
import { AppState } from '../core/store';
import * as ChatActions from '../core/store/chat/chat.actions';
import { ChatMessage, Source } from '../core/services/chat.service';
import { SourcePanelComponent } from '../shared/source-panel/source-panel.component';
import { FeedbackComponent } from '../shared/feedback/feedback.component';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, SourcePanelComponent, FeedbackComponent],
  template: `
    <div class="chat-container">
      <div class="messages" #messagesEl>
        <div class="welcome" *ngIf="(messages$ | async)?.length === 0">
          <div class="welcome-icon">🎓</div>
          <h2>AI Professor</h2>
          <p>Seu assistente de conhecimento corporativo. Faça uma pergunta sobre políticas, processos ou documentos da empresa.</p>
        </div>
        <div class="message-wrapper" *ngFor="let msg of messages$ | async" [class]="msg.role">
          <div class="message-bubble">
            <div class="message-content" [class.loading]="msg.loading">
              {{ msg.content }}
              <span class="cursor" *ngIf="msg.loading">▋</span>
            </div>
            <div class="message-error" *ngIf="msg.error">⚠️ {{ msg.error }}</div>
            <app-source-panel *ngIf="msg.sources?.length" [sources]="msg.sources!" />
            <app-feedback *ngIf="msg.role === 'assistant' && !msg.loading && msg.content"
              [messageId]="msg.id" />
          </div>
        </div>
      </div>

      <div class="input-area">
        <div class="input-wrapper">
          <textarea
            [(ngModel)]="question"
            placeholder="Faça uma pergunta..."
            rows="1"
            (keydown.enter)="onEnter($event)"
            [disabled]="(loading$ | async) === true"
          ></textarea>
          <button class="send-btn"
            (click)="send()"
            [disabled]="!question.trim() || (loading$ | async) === true">
            <span *ngIf="!(loading$ | async)">➤</span>
            <span *ngIf="loading$ | async" class="spinner">⟳</span>
          </button>
        </div>
        <div class="input-footer">
          <span>Enter para enviar · Shift+Enter para nova linha</span>
          <button class="clear-btn" (click)="clear()">Limpar conversa</button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .chat-container { display: flex; flex-direction: column; height: calc(100vh - 52px); }
    .messages { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
    .welcome { text-align: center; margin: auto; max-width: 480px; padding: 48px 24px; }
    .welcome-icon { font-size: 48px; margin-bottom: 16px; }
    .welcome h2 { font-size: 24px; font-weight: 700; color: #1a73e8; margin: 0 0 8px; }
    .welcome p { color: #666; line-height: 1.6; margin: 0; }
    .message-wrapper { display: flex; }
    .message-wrapper.user { justify-content: flex-end; }
    .message-wrapper.assistant { justify-content: flex-start; }
    .message-bubble { max-width: 72%; padding: 12px 16px; border-radius: 16px; font-size: 14px; line-height: 1.6; }
    .user .message-bubble { background: #1a73e8; color: #fff; border-bottom-right-radius: 4px; }
    .assistant .message-bubble { background: #fff; color: #333; border-bottom-left-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .message-content.loading { opacity: 0.8; }
    .cursor { animation: blink 1s infinite; }
    @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
    .message-error { color: #d32f2f; font-size: 12px; margin-top: 6px; }
    .input-area { padding: 16px 24px; background: #fff; border-top: 1px solid #e8eaed; }
    .input-wrapper { display: flex; gap: 8px; align-items: flex-end; }
    textarea { flex: 1; padding: 12px 16px; border: 1px solid #dadce0; border-radius: 24px; font-size: 14px; resize: none; outline: none; font-family: inherit; line-height: 1.5; max-height: 120px; }
    textarea:focus { border-color: #1a73e8; box-shadow: 0 0 0 2px rgba(26,115,232,0.15); }
    .send-btn { width: 44px; height: 44px; border-radius: 50%; background: #1a73e8; color: #fff; border: none; cursor: pointer; font-size: 16px; display: flex; align-items: center; justify-content: center; transition: all 0.15s; flex-shrink: 0; }
    .send-btn:hover:not(:disabled) { background: #1557b0; transform: scale(1.05); }
    .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .spinner { animation: spin 1s linear infinite; display: inline-block; }
    @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
    .input-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; font-size: 11px; color: #888; }
    .clear-btn { background: none; border: none; color: #888; cursor: pointer; font-size: 11px; padding: 0; }
    .clear-btn:hover { color: #d32f2f; }
  `],
})
export class ChatComponent implements AfterViewChecked {
  private store = inject(Store<AppState>);
  @ViewChild('messagesEl') messagesEl!: ElementRef;

  messages$ = this.store.select(s => s.chat.messages);
  loading$  = this.store.select(s => s.chat.loading);
  question  = '';

  private conversationId = crypto.randomUUID();

  ngAfterViewChecked() {
    if (this.messagesEl) {
      const el = this.messagesEl.nativeElement;
      el.scrollTop = el.scrollHeight;
    }
  }

  send() {
    const q = this.question.trim();
    if (!q) return;
    this.question = '';
    this.store.dispatch(ChatActions.sendMessage({ question: q, conversationId: this.conversationId }));
  }

  onEnter(event: KeyboardEvent) {
    if (!event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  onFeedback(data: { messageId: string; positive: boolean }) {
    // Handled by FeedbackComponent internally
  }

  clear() {
    this.store.dispatch(ChatActions.clearHistory());
    this.conversationId = crypto.randomUUID();
  }
}
