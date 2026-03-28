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
import { Component, signal, inject, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpEventType } from '@angular/common/http';
import { TeamsAuthService } from '../core/auth/teams-auth.service';
import { environment } from '../../environments/environment';

interface UploadJob {
  id: string;
  fileName: string;
  fileSize: number;
  status: 'uploading' | 'processing' | 'ready' | 'error';
  progress: number;
  error?: string;
}

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="upload-page">
      <h1 class="page-title">📤 Adicionar Conhecimento</h1>
      <p class="page-desc">Arraste arquivos ou clique para selecionar. O conteúdo ficará disponível para consulta assim que processado.</p>

      <!-- Drop Zone -->
      <div class="drop-zone"
           [class.dragging]="isDragging()"
           [class.has-files]="jobs().length > 0"
           (dragover)="$event.preventDefault(); isDragging.set(true)"
           (dragleave)="isDragging.set(false)"
           (drop)="onDrop($event)">
        <div *ngIf="!isDragging()" class="drop-content">
          <span class="drop-icon">☁️</span>
          <p>Arraste arquivos aqui</p>
          <span class="drop-hint">PDF, DOCX, PPTX, MP4, MP3, WAV — até 2 GB</span>
          <label class="browse-btn">
            Selecionar arquivos
            <input type="file" multiple (change)="onFileSelect($event)" hidden
                   accept=".pdf,.docx,.pptx,.mp4,.mp3,.wav,.xlsx"/>
          </label>
        </div>
        <div *ngIf="isDragging()" class="drop-content dropping">
          <span class="drop-icon">🎯</span>
          <p>Solte para adicionar</p>
        </div>
      </div>

      <!-- Job List -->
      <div *ngIf="jobs().length > 0" class="job-list">
        <div *ngFor="let job of jobs()" class="job-item" [class]="job.status">
          <span class="job-icon">{{ statusIcon(job.status) }}</span>
          <div class="job-info">
            <span class="job-name">{{ job.fileName }}</span>
            <span class="job-size">{{ formatSize(job.fileSize) }}</span>
          </div>
          <div class="job-status">
            <div *ngIf="job.status === 'uploading'" class="progress-bar">
              <div class="progress-fill" [style.width.%]="job.progress"></div>
            </div>
            <span *ngIf="job.status === 'processing'" class="status-text processing">
              Processando...
            </span>
            <span *ngIf="job.status === 'ready'" class="status-text ready">
              ✅ Disponível para consulta
            </span>
            <span *ngIf="job.status === 'error'" class="status-text error">
              ❌ {{ job.error }}
            </span>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .upload-page { padding: 24px; max-width: 720px; margin: 0 auto; }
    .page-title { font-size: 22px; font-weight: 600; color: var(--colorNeutralForeground1); margin: 0 0 8px; }
    .page-desc { font-size: 14px; color: var(--colorNeutralForeground2); margin: 0 0 24px; }

    .drop-zone { border: 2px dashed var(--colorNeutralStroke1); border-radius: 12px; padding: 40px 24px; text-align: center; transition: all 0.2s; cursor: pointer; }
    .drop-zone.dragging { border-color: var(--colorBrandStroke1); background: var(--colorBrandBackground2); transform: scale(1.01); }
    .drop-content { display: flex; flex-direction: column; align-items: center; gap: 8px; }
    .drop-icon { font-size: 40px; }
    .drop-content p { font-size: 16px; font-weight: 500; color: var(--colorNeutralForeground1); margin: 0; }
    .drop-hint { font-size: 12px; color: var(--colorNeutralForeground3); }
    .browse-btn { margin-top: 8px; padding: 8px 20px; background: var(--colorBrandBackground); color: var(--colorNeutralForegroundOnBrand); border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; }

    .job-list { margin-top: 24px; display: flex; flex-direction: column; gap: 8px; }
    .job-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 8px; border: 1px solid var(--colorNeutralStroke2); background: var(--colorNeutralBackground2); }
    .job-icon { font-size: 20px; flex-shrink: 0; }
    .job-info { flex: 1; display: flex; flex-direction: column; min-width: 0; }
    .job-name { font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .job-size { font-size: 12px; color: var(--colorNeutralForeground3); }
    .job-status { min-width: 180px; }
    .progress-bar { height: 6px; background: var(--colorNeutralBackground4); border-radius: 3px; overflow: hidden; }
    .progress-fill { height: 100%; background: var(--colorBrandBackground); border-radius: 3px; transition: width 0.3s; }
    .status-text { font-size: 13px; }
    .status-text.processing { color: var(--colorBrandForeground1); }
    .status-text.ready { color: #059669; }
    .status-text.error { color: #dc2626; }
  `],
})
export class UploadComponent {
  private http = inject(HttpClient);
  private auth = inject(TeamsAuthService);

  jobs       = signal<UploadJob[]>([]);
  isDragging = signal(false);

  onDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragging.set(false);
    const files = event.dataTransfer?.files;
    if (files) this.processFiles(files);
  }

  onFileSelect(event: Event) {
    const files = (event.target as HTMLInputElement).files;
    if (files) this.processFiles(files);
  }

  private processFiles(files: FileList) {
    Array.from(files).forEach(file => {
      const job: UploadJob = {
        id: crypto.randomUUID(),
        fileName: file.name,
        fileSize: file.size,
        status: 'uploading',
        progress: 0,
      };
      this.jobs.update(j => [...j, job]);
      this.upload(file, job.id);
    });
  }

  private upload(file: File, jobId: string) {
    const form = new FormData();
    form.append('file', file);

    this.http.post(`${environment.apiUrl}/ingest/upload`, form, {
      reportProgress: true,
      observe: 'events',
    }).subscribe({
      next: event => {
        if (event.type === HttpEventType.UploadProgress) {
          const pct = Math.round(100 * (event.loaded / (event.total ?? 1)));
          this.updateJob(jobId, { progress: pct });
        }
        if (event.type === HttpEventType.Response) {
          this.updateJob(jobId, { status: 'processing', progress: 100 });
          this.pollStatus(jobId, (event.body as any).job_id);
        }
      },
      error: () => this.updateJob(jobId, { status: 'error', error: 'Falha no upload' }),
    });
  }

  private pollStatus(uiJobId: string, serverJobId: string) {
    const interval = setInterval(() => {
      this.http.get<{ status: string; error?: string }>(
        `${environment.apiUrl}/ingest/status/${serverJobId}`
      ).subscribe(res => {
        if (res.status === 'ready') {
          this.updateJob(uiJobId, { status: 'ready' });
          clearInterval(interval);
        }
        if (res.status === 'error') {
          this.updateJob(uiJobId, { status: 'error', error: res.error });
          clearInterval(interval);
        }
      });
    }, 3000);
  }

  private updateJob(id: string, patch: Partial<UploadJob>) {
    this.jobs.update(jobs => jobs.map(j => j.id === id ? { ...j, ...patch } : j));
  }

  statusIcon(status: string): string {
    return { uploading: '⬆️', processing: '⚙️', ready: '✅', error: '❌' }[status] ?? '📄';
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }
}
