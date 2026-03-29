// src/app/shared/source-panel/source-panel.component.ts
import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Source } from '../../core/services/chat.service';

function formatSeconds(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`;
}

@Component({
  selector: 'app-source-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="sources" *ngIf="sources?.length">
      <div class="sources-title">Fontes</div>
      <div class="source-item" *ngFor="let s of sources; let i = index">
        <a [href]="s.url" target="_blank" rel="noopener" class="source-link">
          <span class="source-num">{{ i + 1 }}</span>
          <span class="source-name">{{ s.name }}</span>
          <span class="source-meta" *ngIf="s.page">p. {{ s.page }}</span>
          <span class="source-meta" *ngIf="s.timestamp_start != null">
            {{ formatSec(s.timestamp_start) }}
          </span>
        </a>
      </div>
    </div>
  `,
  styles: [`
    .sources { margin-top: 12px; border-top: 1px solid rgba(0,0,0,0.08); padding-top: 10px; }
    .sources-title { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 6px; }
    .source-item { margin-bottom: 4px; }
    .source-link { display: flex; align-items: center; gap: 6px; text-decoration: none; color: inherit; padding: 4px 6px; border-radius: 4px; font-size: 13px; }
    .source-link:hover { background: rgba(0,0,0,0.04); }
    .source-num { width: 18px; height: 18px; border-radius: 50%; background: #e8f0fe; color: #1a73e8; font-size: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-weight: 600; }
    .source-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .source-meta { font-size: 11px; color: #888; }
  `],
})
export class SourcePanelComponent {
  @Input() sources: Source[] = [];
  @Output() sourceClicked = new EventEmitter<Source>();

  formatSec = formatSeconds;
}
