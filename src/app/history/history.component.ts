// src/app/history/history.component.ts
import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ChatService, ConversationHistory } from '../core/services/chat.service';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="history-page">
      <div class="page-header">
        <h1>📜 Histórico de Conversas</h1>
      </div>
      <div class="loading" *ngIf="loading()">Carregando...</div>
      <div class="empty" *ngIf="!loading() && conversations().length === 0">
        <p>Nenhuma conversa encontrada.</p>
      </div>
      <div class="conv-list" *ngIf="!loading()">
        <div class="conv-item" *ngFor="let conv of conversations()" (click)="open(conv)">
          <div class="conv-title">{{ getTitle(conv) }}</div>
          <div class="conv-meta">
            <span>{{ conv.messages.length }} mensagens</span>
            <span>{{ conv.updated_at | date:'dd/MM/yyyy HH:mm' }}</span>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .history-page { padding: 24px; max-width: 800px; margin: 0 auto; }
    .page-header h1 { font-size: 24px; margin: 0 0 24px; }
    .loading, .empty { text-align: center; color: #888; padding: 48px; }
    .conv-list { display: flex; flex-direction: column; gap: 8px; }
    .conv-item { padding: 16px; background: #fff; border-radius: 8px; cursor: pointer; border: 1px solid #e8eaed; transition: all 0.15s; }
    .conv-item:hover { border-color: #1a73e8; box-shadow: 0 2px 8px rgba(26,115,232,0.1); }
    .conv-title { font-weight: 500; margin-bottom: 6px; }
    .conv-meta { display: flex; gap: 16px; font-size: 12px; color: #888; }
  `],
})
export class HistoryComponent implements OnInit {
  private chatSvc = inject(ChatService);
  private router  = inject(Router);

  conversations = signal<ConversationHistory[]>([]);
  loading = signal(true);

  ngOnInit() {
    this.chatSvc.getHistory(0, 20).subscribe({
      next: (convs: ConversationHistory[]) => {
        this.conversations.set(convs);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  getTitle(conv: ConversationHistory): string {
    const first = conv.messages.find((m: any) => m.role === 'user');
    return first ? first.content.slice(0, 80) : conv.id;
  }

  open(conv: ConversationHistory) {
    this.router.navigate(['/chat'], { queryParams: { id: conv.id } });
  }
}
