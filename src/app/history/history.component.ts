// src/app/history/history.component.ts
import { Component, OnInit, signal, inject, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ChatService, ConversationHistory } from '../core/services/chat.service';
import { Subject, debounceTime, distinctUntilChanged, switchMap } from 'rxjs';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="history-page">
      <div class="page-header">
        <div>
          <h1 class="page-title">🕐 Histórico de Conversas</h1>
          <p class="page-desc">{{ total() }} conversas registradas</p>
        </div>
        <div class="header-actions">
          <input
            class="search-input"
            [(ngModel)]="searchQuery"
            (ngModelChange)="onSearch($event)"
            placeholder="Buscar em conversas..."
          />
          <button class="btn-outline" (click)="exportAll()">⬇️ Exportar</button>
        </div>
      </div>

      <!-- Loading -->
      <div *ngIf="loading()" class="loading-state">
        <div class="skeleton" *ngFor="let i of [1,2,3,4,5]"></div>
      </div>

      <!-- Empty -->
      <div *ngIf="!loading() && conversations().length === 0" class="empty-state">
        <span class="empty-icon">💬</span>
        <p>Nenhuma conversa encontrada.</p>
      </div>

      <!-- List -->
      <div *ngIf="!loading()" class="conversation-list">
        <div
          *ngFor="let conv of conversations()"
          class="conv-card"
          (click)="openConversation(conv.id)">

          <div class="conv-main">
            <span class="conv-title">{{ conv.title || 'Conversa sem título' }}</span>
            <span class="conv-preview">{{ getPreview(conv) }}</span>
          </div>

          <div class="conv-meta">
            <span class="conv-count">{{ conv.messages.length }} mensagens</span>
            <span class="conv-date">{{ conv.updated_at | date:'dd/MM/yyyy HH:mm' }}</span>
            <button class="btn-icon" (click)="exportConv($event, conv)" title="Exportar">⬇️</button>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div *ngIf="totalPages() > 1" class="pagination">
        <button class="page-btn" [disabled]="currentPage() === 0" (click)="goToPage(currentPage() - 1)">
          ← Anterior
        </button>
        <span class="page-info">{{ currentPage() + 1 }} / {{ totalPages() }}</span>
        <button class="page-btn" [disabled]="currentPage() >= totalPages() - 1" (click)="goToPage(currentPage() + 1)">
          Próxima →
        </button>
      </div>
    </div>
  `,
  styles: [`
    .history-page { padding: 24px; max-width: 860px; margin: 0 auto; height: 100%; overflow-y: auto; }

    .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; gap: 16px; flex-wrap: wrap; }
    .page-title { font-size: 22px; font-weight: 600; color: var(--colorNeutralForeground1); margin: 0 0 4px; }
    .page-desc { font-size: 13px; color: var(--colorNeutralForeground3); margin: 0; }
    .header-actions { display: flex; gap: 10px; align-items: center; }

    .search-input { padding: 8px 14px; border: 1px solid var(--colorNeutralStroke1); border-radius: 6px; font-size: 14px; background: var(--colorNeutralBackground2); color: var(--colorNeutralForeground1); outline: none; min-width: 220px; }
    .search-input:focus { border-color: var(--colorBrandStroke1); }

    .btn-outline { padding: 7px 14px; border: 1px solid var(--colorNeutralStroke1); border-radius: 6px; background: transparent; color: var(--colorNeutralForeground2); font-size: 13px; cursor: pointer; }
    .btn-outline:hover { background: var(--colorNeutralBackground3); }

    .skeleton { height: 72px; background: linear-gradient(90deg, var(--colorNeutralBackground3) 25%, var(--colorNeutralBackground4) 50%, var(--colorNeutralBackground3) 75%); background-size: 200% 100%; animation: shimmer 1.4s infinite; border-radius: 8px; margin-bottom: 8px; }
    @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

    .empty-state { text-align: center; padding: 60px 20px; color: var(--colorNeutralForeground3); }
    .empty-icon { font-size: 40px; display: block; margin-bottom: 12px; }

    .conversation-list { display: flex; flex-direction: column; gap: 8px; }
    .conv-card { display: flex; align-items: center; gap: 16px; padding: 14px 18px; border: 1px solid var(--colorNeutralStroke2); border-radius: 8px; background: var(--colorNeutralBackground2); cursor: pointer; transition: all 0.13s; }
    .conv-card:hover { border-color: var(--colorBrandStroke1); background: var(--colorBrandBackground2); transform: translateX(2px); }

    .conv-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
    .conv-title { font-size: 14px; font-weight: 600; color: var(--colorNeutralForeground1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .conv-preview { font-size: 13px; color: var(--colorNeutralForeground3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .conv-meta { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
    .conv-count { font-size: 12px; color: var(--colorNeutralForeground3); }
    .conv-date { font-size: 12px; color: var(--colorNeutralForeground3); }
    .btn-icon { background: none; border: none; cursor: pointer; font-size: 16px; padding: 4px; border-radius: 4px; }
    .btn-icon:hover { background: var(--colorNeutralBackground4); }

    .pagination { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 24px; }
    .page-btn { padding: 7px 16px; border: 1px solid var(--colorNeutralStroke1); border-radius: 6px; background: transparent; color: var(--colorNeutralForeground1); font-size: 13px; cursor: pointer; }
    .page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    .page-btn:not(:disabled):hover { background: var(--colorBrandBackground2); border-color: var(--colorBrandStroke1); }
    .page-info { font-size: 13px; color: var(--colorNeutralForeground2); }
  `],
})
export class HistoryComponent implements OnInit {
  private chatSvc = inject(ChatService);
  private router  = inject(Router);

  conversations = signal<ConversationHistory[]>([]);
  loading       = signal(true);
  currentPage   = signal(0);
  total         = signal(0);
  searchQuery   = '';

  private searchSubject = new Subject<string>();
  readonly PAGE_SIZE = 20;
  totalPages = computed(() => Math.ceil(this.total() / this.PAGE_SIZE));

  ngOnInit() {
    this.loadPage(0);

    this.searchSubject.pipe(
      debounceTime(350),
      distinctUntilChanged(),
    ).subscribe(q => this.loadPage(0, q));
  }

  loadPage(page: number, search = '') {
    this.loading.set(true);
    this.chatSvc.getHistory(page, this.PAGE_SIZE).subscribe({
      next: convs => {
        this.conversations.set(convs);
        this.currentPage.set(page);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  onSearch(q: string) { this.searchSubject.next(q); }
  goToPage(p: number) { this.loadPage(p, this.searchQuery); }

  openConversation(id: string) {
    this.router.navigate(['/chat'], { queryParams: { conversationId: id } });
  }

  getPreview(conv: ConversationHistory): string {
    const first = conv.messages.find(m => m.role === 'user');
    return first?.content?.slice(0, 100) ?? '—';
  }

  exportConv(event: Event, conv: ConversationHistory) {
    event.stopPropagation();
    const lines = conv.messages.map(m =>
      `[${m.role.toUpperCase()}] ${new Date(m.timestamp).toLocaleString('pt-BR')}\n${m.content}\n`
    );
    const blob = new Blob([lines.join('\n---\n')], { type: 'text/plain;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = Object.assign(document.createElement('a'), { href: url, download: `conversa-${conv.id}.txt` });
    a.click();
    URL.revokeObjectURL(url);
  }

  exportAll() {
    // Export all visible conversations as JSON
    const data = JSON.stringify(this.conversations(), null, 2);
    const blob  = new Blob([data], { type: 'application/json' });
    const url   = URL.createObjectURL(blob);
    const a     = Object.assign(document.createElement('a'), { href: url, download: 'historico-ai-professor.json' });
    a.click();
    URL.revokeObjectURL(url);
  }
}
