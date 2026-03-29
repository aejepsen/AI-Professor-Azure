// src/app/shared/source-panel/source-panel.component.ts
import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { AnswerSource } from '../../core/services/chat.service';

function formatSeconds(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return h > 0
    ? `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
    : `${m}:${String(sec).padStart(2,'0')}`;
}

@Component({
  selector: 'app-source-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="sources">
      <span class="sources-label">📎 Fontes utilizadas</span>
      <div class="source-list">
        <button *ngFor="let src of sources"
                class="source-item"
                [class]="src.type"
                (click)="src.type === 'video' ? openVideo.emit(src) : openDoc.emit(src)">

          <span class="src-icon">{{ icons[src.type] }}</span>
          <span class="src-info">
            <span class="src-name">{{ src.name }}</span>
            <span class="src-meta" *ngIf="src.type === 'video'">
              {{ formatTs(src.timestamp_start!) }} → {{ formatTs(src.timestamp_end!) }}
            </span>
            <span class="src-meta" *ngIf="src.type === 'document' && src.page">
              Página {{ src.page }}
            </span>
          </span>
          <span class="src-score">{{ (src.relevance_score * 100).toFixed(0) }}%</span>
        </button>
      </div>
    </div>
  `,
  styles: [`
    .sources { margin-top: 8px; }
    .sources-label { font-size: 11px; font-weight: 600; color: var(--colorNeutralForeground3); text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 6px; }
    .source-list { display: flex; flex-direction: column; gap: 4px; }
    .source-item { display: flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--colorNeutralStroke2); background: var(--colorNeutralBackground2); cursor: pointer; text-align: left; width: 100%; transition: all 0.12s; }
    .source-item:hover { background: var(--colorBrandBackground2); border-color: var(--colorBrandStroke1); }
    .src-icon { font-size: 16px; flex-shrink: 0; }
    .src-info { flex: 1; display: flex; flex-direction: column; min-width: 0; }
    .src-name { font-size: 13px; font-weight: 500; color: var(--colorNeutralForeground1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .src-meta { font-size: 11px; color: var(--colorBrandForeground1); font-weight: 600; }
    .src-score { font-size: 11px; color: var(--colorNeutralForeground3); flex-shrink: 0; }
  `],
})
export class SourcePanelComponent {
  @Input() sources: AnswerSource[] = [];
  @Output() openVideo = new EventEmitter<AnswerSource>();
  @Output() openDoc   = new EventEmitter<AnswerSource>();

  icons: Record<string, string> = {
    video: '▶️', document: '📄', policy: '📋',
  };

  formatTs = formatSeconds;
}


// ─────────────────────────────────────────────────────────────────────────────
// src/app/upload/upload.component.ts
// ─────────────────────────────────────────────────────────────────────────────
