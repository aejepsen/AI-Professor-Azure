// src/app/knowledge/knowledge.component.ts
import { Component, OnInit, signal, inject, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

export interface KnowledgeItem {
  id: string;
  name: string;
  type: 'video' | 'document' | 'policy' | 'presentation';
  sensitivity_label: 'public' | 'internal' | 'confidential' | 'restricted';
  topics: string[];
  summary: string;
  source_url: string;
  quality_score: number;
  chunks_count: number;
  updated_at: string;
  duration_seconds?: number;  // videos
  page_count?: number;         // documents
}

const TYPE_ICON: Record<string, string> = {
  video: '🎬', document: '📄', policy: '📋', presentation: '📊',
};
const LABEL_COLOR: Record<string, string> = {
  public: '#059669', internal: '#0ea5e9', confidential: '#d97706', restricted: '#dc2626',
};

@Component({
  selector: 'app-knowledge',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="knowledge-page">

      <!-- Header + Filters -->
      <div class="page-header">
        <div>
          <h1 class="page-title">📚 Base de Conhecimento</h1>
          <p class="page-desc">{{ filtered().length }} itens disponíveis</p>
        </div>
      </div>

      <div class="filter-bar">
        <input class="search-input" [(ngModel)]="search" placeholder="Buscar por nome, tópico ou resumo..." />
        <select class="filter-select" [(ngModel)]="typeFilter">
          <option value="">Todos os tipos</option>
          <option value="video">Vídeos</option>
          <option value="document">Documentos</option>
          <option value="policy">Políticas</option>
          <option value="presentation">Apresentações</option>
        </select>
        <select class="filter-select" [(ngModel)]="labelFilter">
          <option value="">Todas as visibilidades</option>
          <option value="public">Público</option>
          <option value="internal">Interno</option>
          <option value="confidential">Confidencial</option>
        </select>
        <div class="view-toggle">
          <button [class.active]="viewMode() === 'grid'" (click)="viewMode.set('grid')">⊞</button>
          <button [class.active]="viewMode() === 'list'" (click)="viewMode.set('list')">☰</button>
        </div>
      </div>

      <!-- Topic chips -->
      <div class="topics-row">
        <button
          *ngFor="let topic of allTopics()"
          class="topic-chip"
          [class.active]="topicFilter === topic"
          (click)="toggleTopic(topic)">
          {{ topic }}
        </button>
      </div>

      <!-- Loading -->
      <div *ngIf="loading()" class="grid-view">
        <div class="skeleton-card" *ngFor="let i of [1,2,3,4,5,6]"></div>
      </div>

      <!-- Grid view -->
      <div *ngIf="!loading() && viewMode() === 'grid'" class="grid-view">
        <div *ngFor="let item of filtered()" class="item-card" (click)="openItem(item)">
          <div class="card-header" [style.background]="typeGradient(item.type)">
            <span class="type-icon">{{ icon(item.type) }}</span>
            <span class="sensitivity-badge" [style.background]="labelBg(item.sensitivity_label)">
              {{ item.sensitivity_label }}
            </span>
          </div>
          <div class="card-body">
            <p class="item-name">{{ item.name }}</p>
            <p class="item-summary">{{ item.summary | slice:0:100 }}{{ item.summary.length > 100 ? '…' : '' }}</p>
            <div class="item-topics">
              <span *ngFor="let t of item.topics.slice(0,3)" class="mini-chip">{{ t }}</span>
            </div>
          </div>
          <div class="card-footer">
            <span class="quality" [style.color]="qualityColor(item.quality_score)">
              ★ {{ (item.quality_score * 100).toFixed(0) }}%
            </span>
            <span class="chunks">{{ item.chunks_count }} chunks</span>
            <span class="date">{{ item.updated_at | date:'dd/MM/yy' }}</span>
          </div>
        </div>
      </div>

      <!-- List view -->
      <div *ngIf="!loading() && viewMode() === 'list'" class="list-view">
        <div *ngFor="let item of filtered()" class="list-row" (click)="openItem(item)">
          <span class="list-icon">{{ icon(item.type) }}</span>
          <div class="list-info">
            <span class="list-name">{{ item.name }}</span>
            <span class="list-topics">{{ item.topics.slice(0,4).join(' · ') }}</span>
          </div>
          <span class="sensitivity-badge sm" [style.background]="labelBg(item.sensitivity_label)">
            {{ item.sensitivity_label }}
          </span>
          <span class="quality sm" [style.color]="qualityColor(item.quality_score)">
            ★ {{ (item.quality_score * 100).toFixed(0) }}%
          </span>
          <span class="date sm">{{ item.updated_at | date:'dd/MM/yy' }}</span>
        </div>
      </div>

      <!-- Empty -->
      <div *ngIf="!loading() && filtered().length === 0" class="empty-state">
        <span>🔍</span>
        <p>Nenhum item encontrado. Tente outros filtros.</p>
      </div>

    </div>
  `,
  styles: [`
    .knowledge-page { padding: 24px; height: 100%; overflow-y: auto; }
    .page-header { margin-bottom: 16px; }
    .page-title { font-size: 22px; font-weight: 600; color: var(--colorNeutralForeground1); margin: 0 0 4px; }
    .page-desc { font-size: 13px; color: var(--colorNeutralForeground3); margin: 0; }

    .filter-bar { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }
    .search-input { flex: 1; min-width: 200px; padding: 8px 14px; border: 1px solid var(--colorNeutralStroke1); border-radius: 6px; font-size: 14px; background: var(--colorNeutralBackground2); color: var(--colorNeutralForeground1); outline: none; }
    .search-input:focus { border-color: var(--colorBrandStroke1); }
    .filter-select { padding: 8px 12px; border: 1px solid var(--colorNeutralStroke1); border-radius: 6px; font-size: 13px; background: var(--colorNeutralBackground2); color: var(--colorNeutralForeground1); cursor: pointer; }
    .view-toggle { display: flex; border: 1px solid var(--colorNeutralStroke1); border-radius: 6px; overflow: hidden; }
    .view-toggle button { padding: 7px 12px; border: none; background: var(--colorNeutralBackground2); color: var(--colorNeutralForeground2); cursor: pointer; font-size: 16px; }
    .view-toggle button.active { background: var(--colorBrandBackground); color: white; }

    .topics-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
    .topic-chip { padding: 4px 12px; border-radius: 14px; border: 1px solid var(--colorNeutralStroke1); background: var(--colorNeutralBackground2); color: var(--colorNeutralForeground2); font-size: 12px; cursor: pointer; transition: all 0.12s; }
    .topic-chip:hover, .topic-chip.active { background: var(--colorBrandBackground2); border-color: var(--colorBrandStroke1); color: var(--colorBrandForeground1); }

    /* Grid */
    .grid-view { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
    .item-card { border: 1px solid var(--colorNeutralStroke2); border-radius: 10px; overflow: hidden; background: var(--colorNeutralBackground2); cursor: pointer; transition: all 0.15s; display: flex; flex-direction: column; }
    .item-card:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.1); border-color: var(--colorBrandStroke1); }

    .card-header { padding: 20px; display: flex; justify-content: space-between; align-items: flex-start; }
    .type-icon { font-size: 32px; }
    .sensitivity-badge { padding: 3px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; color: white; text-transform: uppercase; }
    .sensitivity-badge.sm { padding: 2px 7px; font-size: 10px; }

    .card-body { padding: 0 16px 12px; flex: 1; }
    .item-name { font-size: 14px; font-weight: 600; color: var(--colorNeutralForeground1); margin: 0 0 6px; line-height: 1.4; }
    .item-summary { font-size: 12px; color: var(--colorNeutralForeground3); margin: 0 0 10px; line-height: 1.5; }
    .item-topics { display: flex; gap: 4px; flex-wrap: wrap; }
    .mini-chip { padding: 2px 8px; border-radius: 10px; background: var(--colorNeutralBackground4); color: var(--colorNeutralForeground2); font-size: 11px; }

    .card-footer { display: flex; align-items: center; gap: 10px; padding: 10px 16px; border-top: 1px solid var(--colorNeutralStroke2); font-size: 12px; color: var(--colorNeutralForeground3); }
    .quality { font-weight: 600; margin-right: auto; }
    .chunks, .date { color: var(--colorNeutralForeground3); }

    /* List */
    .list-view { display: flex; flex-direction: column; gap: 6px; }
    .list-row { display: flex; align-items: center; gap: 14px; padding: 12px 16px; border: 1px solid var(--colorNeutralStroke2); border-radius: 8px; background: var(--colorNeutralBackground2); cursor: pointer; transition: all 0.12s; }
    .list-row:hover { border-color: var(--colorBrandStroke1); background: var(--colorBrandBackground2); }
    .list-icon { font-size: 22px; flex-shrink: 0; }
    .list-info { flex: 1; min-width: 0; }
    .list-name { font-size: 14px; font-weight: 500; color: var(--colorNeutralForeground1); display: block; }
    .list-topics { font-size: 12px; color: var(--colorNeutralForeground3); }
    .quality.sm { font-size: 12px; font-weight: 600; flex-shrink: 0; }
    .date.sm { font-size: 12px; color: var(--colorNeutralForeground3); flex-shrink: 0; }

    /* Skeleton */
    .skeleton-card { height: 220px; background: linear-gradient(90deg, var(--colorNeutralBackground3) 25%, var(--colorNeutralBackground4) 50%, var(--colorNeutralBackground3) 75%); background-size: 200% 100%; animation: shimmer 1.4s infinite; border-radius: 10px; }
    @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

    .empty-state { text-align: center; padding: 60px; color: var(--colorNeutralForeground3); font-size: 40px; }
    .empty-state p { font-size: 14px; margin-top: 12px; }
  `],
})
export class KnowledgeComponent implements OnInit {
  private http = inject(HttpClient);

  items     = signal<KnowledgeItem[]>([]);
  loading   = signal(true);
  viewMode  = signal<'grid' | 'list'>('grid');
  search    = '';
  typeFilter  = '';
  labelFilter = '';
  topicFilter = '';

  allTopics = computed(() => {
    const set = new Set<string>();
    this.items().forEach(i => i.topics.forEach(t => set.add(t)));
    return Array.from(set).sort();
  });

  filtered = computed(() => {
    let list = this.items();
    if (this.search)      list = list.filter(i =>
      i.name.toLowerCase().includes(this.search.toLowerCase()) ||
      i.summary.toLowerCase().includes(this.search.toLowerCase()) ||
      i.topics.some(t => t.toLowerCase().includes(this.search.toLowerCase()))
    );
    if (this.typeFilter)  list = list.filter(i => i.type === this.typeFilter);
    if (this.labelFilter) list = list.filter(i => i.sensitivity_label === this.labelFilter);
    if (this.topicFilter) list = list.filter(i => i.topics.includes(this.topicFilter));
    return list;
  });

  ngOnInit() {
    this.http.get<KnowledgeItem[]>(`${environment.apiUrl}/knowledge`).subscribe({
      next:  items => { this.items.set(items); this.loading.set(false); },
      error: ()    => this.loading.set(false),
    });
  }

  toggleTopic(topic: string) {
    this.topicFilter = this.topicFilter === topic ? '' : topic;
  }

  openItem(item: KnowledgeItem) {
    window.open(item.source_url, '_blank');
  }

  icon(type: string)   { return TYPE_ICON[type] ?? '📄'; }
  labelBg(label: string) { return LABEL_COLOR[label] ?? '#64748b'; }

  qualityColor(score: number): string {
    if (score >= 0.9) return '#059669';
    if (score >= 0.75) return '#d97706';
    return '#dc2626';
  }

  typeGradient(type: string): string {
    const map: Record<string, string> = {
      video:        'linear-gradient(135deg, #0f2d5e, #1a56db)',
      document:     'linear-gradient(135deg, #0d4f3c, #059669)',
      policy:       'linear-gradient(135deg, #7c2d12, #d97706)',
      presentation: 'linear-gradient(135deg, #4a1d96, #7c3aed)',
    };
    return map[type] ?? 'linear-gradient(135deg, #334155, #64748b)';
  }
}
