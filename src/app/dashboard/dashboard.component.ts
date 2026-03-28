// src/app/dashboard/dashboard.component.ts
import { Component, OnInit, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

interface DashboardMetrics {
  total_conversations: number;
  total_messages:      number;
  avg_response_time_ms: number;
  csat_score:          number;
  resolution_rate:     number;
  ragas: {
    faithfulness:      number;
    answer_relevancy:  number;
    context_recall:    number;
    context_precision: number;
    answer_correctness:number;
  };
  knowledge: {
    total_documents: number;
    total_chunks:    number;
    coverage_pct:    number;
    pending_review:  number;
  };
  top_topics: { topic: string; count: number }[];
  gaps:       { question: string; frequency: number; last_asked: string }[];
  daily_usage: { date: string; conversations: number; messages: number }[];
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="dashboard-page">
      <div class="page-header">
        <h1 class="page-title">📊 Dashboard</h1>
        <p class="page-desc">Métricas de qualidade e uso — últimos 30 dias</p>
        <button class="btn-refresh" (click)="load()" [disabled]="loading()">
          {{ loading() ? 'Carregando...' : '🔄 Atualizar' }}
        </button>
      </div>

      <ng-container *ngIf="!loading() && metrics() as m">

        <!-- KPI Cards -->
        <div class="kpi-grid">
          <div class="kpi-card">
            <span class="kpi-icon">💬</span>
            <div class="kpi-body">
              <span class="kpi-value">{{ m.total_conversations | number }}</span>
              <span class="kpi-label">Conversas</span>
            </div>
          </div>
          <div class="kpi-card">
            <span class="kpi-icon">⚡</span>
            <div class="kpi-body">
              <span class="kpi-value" [style.color]="latencyColor(m.avg_response_time_ms)">
                {{ (m.avg_response_time_ms / 1000).toFixed(1) }}s
              </span>
              <span class="kpi-label">Resposta média (P95)</span>
            </div>
          </div>
          <div class="kpi-card">
            <span class="kpi-icon">⭐</span>
            <div class="kpi-body">
              <span class="kpi-value" [style.color]="csatColor(m.csat_score)">
                {{ m.csat_score.toFixed(1) }}/5.0
              </span>
              <span class="kpi-label">CSAT</span>
            </div>
          </div>
          <div class="kpi-card">
            <span class="kpi-icon">✅</span>
            <div class="kpi-body">
              <span class="kpi-value" [style.color]="rateColor(m.resolution_rate)">
                {{ (m.resolution_rate * 100).toFixed(0) }}%
              </span>
              <span class="kpi-label">Taxa de resolução</span>
            </div>
          </div>
        </div>

        <!-- RAGAS -->
        <div class="section">
          <h2 class="section-title">🧪 Qualidade RAGAS — Últimos 7 dias</h2>
          <div class="ragas-grid">
            <div *ngFor="let metric of ragasMetrics(m.ragas)" class="ragas-card">
              <div class="ragas-bar-wrap">
                <div class="ragas-bar">
                  <div class="ragas-fill"
                       [style.width.%]="metric.value * 100"
                       [style.background]="scoreColor(metric.value)">
                  </div>
                </div>
              </div>
              <div class="ragas-info">
                <span class="ragas-name">{{ metric.label }}</span>
                <span class="ragas-score" [style.color]="scoreColor(metric.value)">
                  {{ (metric.value * 100).toFixed(0) }}%
                </span>
              </div>
              <div class="ragas-target" [class.ok]="metric.value >= metric.target" [class.warn]="metric.value < metric.target">
                {{ metric.value >= metric.target ? '✅ Meta atingida' : '⚠️ Abaixo da meta (' + (metric.target * 100).toFixed(0) + '%)' }}
              </div>
            </div>
          </div>
        </div>

        <!-- Knowledge Coverage -->
        <div class="two-col">
          <div class="section">
            <h2 class="section-title">📚 Base de Conhecimento</h2>
            <div class="stat-list">
              <div class="stat-row">
                <span class="stat-label">Documentos indexados</span>
                <span class="stat-value">{{ m.knowledge.total_documents }}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Total de chunks</span>
                <span class="stat-value">{{ m.knowledge.total_chunks | number }}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Cobertura</span>
                <span class="stat-value" [style.color]="rateColor(m.knowledge.coverage_pct / 100)">
                  {{ m.knowledge.coverage_pct }}%
                </span>
              </div>
              <div class="stat-row" *ngIf="m.knowledge.pending_review > 0">
                <span class="stat-label">⚠️ Aguardando revisão</span>
                <span class="stat-value warn">{{ m.knowledge.pending_review }}</span>
              </div>
            </div>
          </div>

          <div class="section">
            <h2 class="section-title">🔥 Tópicos Mais Consultados</h2>
            <div class="topics-list">
              <div *ngFor="let t of m.top_topics; let i = index" class="topic-row">
                <span class="topic-rank">{{ i + 1 }}</span>
                <span class="topic-name">{{ t.topic }}</span>
                <div class="topic-bar-wrap">
                  <div class="topic-bar"
                       [style.width.%]="(t.count / m.top_topics[0].count) * 100">
                  </div>
                </div>
                <span class="topic-count">{{ t.count }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Gaps -->
        <div class="section" *ngIf="m.gaps.length > 0">
          <h2 class="section-title">🕳️ Gaps Detectados — Perguntas sem Boa Resposta</h2>
          <p class="section-desc">Estas perguntas foram feitas com frequência mas não tiveram resposta com score RAGAS aceitável. Adicione conteúdo à base para resolvê-las.</p>
          <div class="gap-list">
            <div *ngFor="let gap of m.gaps" class="gap-row">
              <div class="gap-main">
                <span class="gap-question">"{{ gap.question }}"</span>
                <span class="gap-date">Última vez: {{ gap.last_asked | date:'dd/MM/yy' }}</span>
              </div>
              <span class="gap-freq">{{ gap.frequency }}x</span>
              <button class="btn-add" (click)="goToUpload()">+ Adicionar conteúdo</button>
            </div>
          </div>
        </div>

      </ng-container>

      <!-- Loading skeleton -->
      <div *ngIf="loading()" class="skeleton-dashboard">
        <div class="kpi-grid">
          <div class="skeleton-kpi" *ngFor="let i of [1,2,3,4]"></div>
        </div>
        <div class="skeleton-section"></div>
        <div class="skeleton-section"></div>
      </div>
    </div>
  `,
  styles: [`
    .dashboard-page { padding: 24px; height: 100%; overflow-y: auto; }
    .page-header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
    .page-title { font-size: 22px; font-weight: 600; color: var(--colorNeutralForeground1); margin: 0 0 4px; }
    .page-desc { font-size: 13px; color: var(--colorNeutralForeground3); margin: 0; flex: 1; }
    .btn-refresh { padding: 7px 16px; border: 1px solid var(--colorNeutralStroke1); border-radius: 6px; background: transparent; color: var(--colorNeutralForeground2); font-size: 13px; cursor: pointer; }
    .btn-refresh:hover:not(:disabled) { background: var(--colorNeutralBackground3); }

    /* KPI Cards */
    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }
    .kpi-card { display: flex; align-items: center; gap: 14px; padding: 18px; border: 1px solid var(--colorNeutralStroke2); border-radius: 10px; background: var(--colorNeutralBackground2); }
    .kpi-icon { font-size: 28px; }
    .kpi-body { display: flex; flex-direction: column; }
    .kpi-value { font-size: 24px; font-weight: 700; color: var(--colorNeutralForeground1); line-height: 1.2; }
    .kpi-label { font-size: 12px; color: var(--colorNeutralForeground3); }

    /* Sections */
    .section { margin-bottom: 24px; }
    .section-title { font-size: 16px; font-weight: 600; color: var(--colorNeutralForeground1); margin: 0 0 12px; }
    .section-desc { font-size: 13px; color: var(--colorNeutralForeground3); margin: -8px 0 14px; }

    .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }

    /* RAGAS */
    .ragas-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; }
    .ragas-card { padding: 16px; border: 1px solid var(--colorNeutralStroke2); border-radius: 8px; background: var(--colorNeutralBackground2); display: flex; flex-direction: column; gap: 8px; }
    .ragas-bar-wrap { background: var(--colorNeutralBackground4); border-radius: 4px; height: 8px; overflow: hidden; }
    .ragas-bar { height: 100%; }
    .ragas-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease; }
    .ragas-info { display: flex; justify-content: space-between; align-items: center; }
    .ragas-name { font-size: 13px; font-weight: 500; color: var(--colorNeutralForeground1); }
    .ragas-score { font-size: 18px; font-weight: 700; }
    .ragas-target { font-size: 11px; padding: 3px 8px; border-radius: 10px; width: fit-content; }
    .ragas-target.ok { background: #d1fae5; color: #065f46; }
    .ragas-target.warn { background: #fef3c7; color: #92400e; }

    /* Stats */
    .stat-list { display: flex; flex-direction: column; gap: 0; border: 1px solid var(--colorNeutralStroke2); border-radius: 8px; overflow: hidden; }
    .stat-row { display: flex; justify-content: space-between; padding: 11px 16px; border-bottom: 1px solid var(--colorNeutralStroke2); }
    .stat-row:last-child { border: none; }
    .stat-label { font-size: 13px; color: var(--colorNeutralForeground2); }
    .stat-value { font-size: 13px; font-weight: 600; color: var(--colorNeutralForeground1); }
    .stat-value.warn { color: #d97706; }

    /* Topics */
    .topics-list { display: flex; flex-direction: column; gap: 8px; }
    .topic-row { display: flex; align-items: center; gap: 10px; }
    .topic-rank { width: 20px; font-size: 12px; font-weight: 700; color: var(--colorNeutralForeground3); text-align: center; }
    .topic-name { min-width: 120px; font-size: 13px; color: var(--colorNeutralForeground1); }
    .topic-bar-wrap { flex: 1; background: var(--colorNeutralBackground4); border-radius: 3px; height: 6px; }
    .topic-bar { height: 100%; background: var(--colorBrandBackground); border-radius: 3px; transition: width 0.5s; }
    .topic-count { font-size: 12px; color: var(--colorNeutralForeground3); min-width: 30px; text-align: right; }

    /* Gaps */
    .gap-list { display: flex; flex-direction: column; gap: 8px; }
    .gap-row { display: flex; align-items: center; gap: 14px; padding: 12px 16px; border: 1px solid #fde68a; border-radius: 8px; background: #fffbeb; }
    .gap-main { flex: 1; min-width: 0; }
    .gap-question { font-size: 13px; font-weight: 500; color: #92400e; display: block; }
    .gap-date { font-size: 11px; color: #b45309; }
    .gap-freq { font-size: 13px; font-weight: 700; color: #d97706; flex-shrink: 0; }
    .btn-add { padding: 6px 12px; background: #d97706; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer; flex-shrink: 0; }
    .btn-add:hover { background: #b45309; }

    /* Skeleton */
    .skeleton-kpi { height: 80px; border-radius: 10px; background: var(--colorNeutralBackground3); animation: shimmer 1.4s infinite; }
    .skeleton-section { height: 180px; border-radius: 8px; background: var(--colorNeutralBackground3); margin-bottom: 24px; animation: shimmer 1.4s infinite; }
    @keyframes shimmer { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }

    @media (max-width: 800px) {
      .kpi-grid { grid-template-columns: repeat(2, 1fr); }
      .two-col  { grid-template-columns: 1fr; }
    }
  `],
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);

  metrics = signal<DashboardMetrics | null>(null);
  loading = signal(true);

  ngOnInit() { this.load(); }

  load() {
    this.loading.set(true);
    this.http.get<DashboardMetrics>(`${environment.apiUrl}/dashboard/metrics`).subscribe({
      next:  m  => { this.metrics.set(m); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  ragasMetrics(ragas: DashboardMetrics['ragas']) {
    return [
      { label: 'Faithfulness',       value: ragas.faithfulness,       target: 0.85 },
      { label: 'Answer Relevancy',   value: ragas.answer_relevancy,   target: 0.80 },
      { label: 'Context Recall',     value: ragas.context_recall,     target: 0.75 },
      { label: 'Context Precision',  value: ragas.context_precision,  target: 0.80 },
      { label: 'Answer Correctness', value: ragas.answer_correctness, target: 0.85 },
    ];
  }

  scoreColor(v: number)    { return v >= 0.85 ? '#059669' : v >= 0.70 ? '#d97706' : '#dc2626'; }
  csatColor(v: number)     { return v >= 4.2 ? '#059669' : v >= 3.5 ? '#d97706' : '#dc2626'; }
  rateColor(v: number)     { return v >= 0.80 ? '#059669' : v >= 0.60 ? '#d97706' : '#dc2626'; }
  latencyColor(ms: number) { return ms <= 4000 ? '#059669' : ms <= 7000 ? '#d97706' : '#dc2626'; }

  goToUpload() { window.location.hash = '/upload'; }
}
