// src/app/upload/upload.component.ts
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Store } from '@ngrx/store';
import { HttpClient } from '@angular/common/http';
import { AppState } from '../core/store';
import * as UploadActions from '../core/store/upload/upload.actions';
import { environment } from '../../environments/environment';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="upload-page">
      <div class="upload-header">
        <h1>📤 Upload de Documentos</h1>
        <p>Adicione documentos, políticas e vídeos à base de conhecimento.</p>
      </div>

      <div
        class="drop-zone"
        [class.dragging]="dragging"
        (dragover)="onDragOver($event)"
        (dragleave)="dragging = false"
        (drop)="onDrop($event)"
        (click)="fileInput.click()"
      >
        <span class="drop-icon">📁</span>
        <p>Arraste arquivos aqui ou clique para selecionar</p>
        <small>PDF, DOCX, MP4 — máximo 200MB</small>
        <input #fileInput type="file" multiple accept=".pdf,.docx,.mp4"
               style="display:none" (change)="onFileSelected($event)">
      </div>

      <div class="jobs-list" *ngIf="(jobs$ | async)?.length">
        <h3>Processamentos</h3>
        <div class="job-item" *ngFor="let job of jobs$ | async">
          <div class="job-info">
            <span class="job-name">{{ job.filename }}</span>
            <span class="job-status" [class]="job.status">{{ statusLabel(job.status) }}</span>
          </div>
          <div class="progress-bar" *ngIf="job.status !== 'completed' && job.status !== 'failed'">
            <div class="progress-fill" [style.width.%]="job.progress"></div>
          </div>
          <p class="error-msg" *ngIf="job.error">{{ job.error }}</p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .upload-page { padding: 24px; max-width: 800px; margin: 0 auto; }
    .upload-header h1 { font-size: 24px; margin: 0 0 8px; }
    .upload-header p { color: var(--colorNeutralForeground3, #666); margin: 0 0 24px; }
    .drop-zone {
      border: 2px dashed var(--colorNeutralStroke1, #ccc);
      border-radius: 12px;
      padding: 48px;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s;
    }
    .drop-zone:hover, .drop-zone.dragging {
      border-color: var(--colorBrandBackground, #0078d4);
      background: var(--colorNeutralBackground2, #f5f5f5);
    }
    .drop-icon { font-size: 48px; display: block; margin-bottom: 12px; }
    .jobs-list { margin-top: 32px; }
    .jobs-list h3 { margin: 0 0 16px; }
    .job-item {
      padding: 12px 16px;
      border: 1px solid var(--colorNeutralStroke2, #e0e0e0);
      border-radius: 8px;
      margin-bottom: 8px;
    }
    .job-info { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .job-name { font-weight: 500; }
    .job-status { font-size: 12px; padding: 2px 8px; border-radius: 4px; }
    .job-status.completed { background: #e6f4ea; color: #137333; }
    .job-status.failed { background: #fce8e6; color: #c5221f; }
    .job-status.uploading, .job-status.indexing, .job-status.extracting { background: #e8f0fe; color: #1a73e8; }
    .progress-bar { height: 4px; background: var(--colorNeutralBackground3, #eee); border-radius: 2px; overflow: hidden; }
    .progress-fill { height: 100%; background: var(--colorBrandBackground, #0078d4); transition: width 0.3s; }
    .error-msg { color: #c5221f; font-size: 12px; margin: 4px 0 0; }
  `],
})
export class UploadComponent {
  private store = inject(Store<AppState>);
  private http  = inject(HttpClient);

  dragging = false;
  jobs$ = this.store.select(state => state.upload.jobs);

  onDragOver(e: DragEvent) {
    e.preventDefault();
    this.dragging = true;
  }

  onDrop(e: DragEvent) {
    e.preventDefault();
    this.dragging = false;
    const files = Array.from(e.dataTransfer?.files ?? []);
    files.forEach(f => this.uploadFile(f));
  }

  onFileSelected(e: Event) {
    const input = e.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    files.forEach(f => this.uploadFile(f));
    input.value = '';
  }

  uploadFile(file: File) {
    const jobId = crypto.randomUUID();
    this.store.dispatch(UploadActions.startUpload({
      job: { id: jobId, filename: file.name, status: 'queued', progress: 0 },
    }));

    const form = new FormData();
    form.append('file', file);

    this.http.post<any>(`${environment.apiUrl}/ingest/upload`, form).subscribe({
      next: res => this.store.dispatch(UploadActions.updateStatus({ id: jobId, status: 'uploading' })),
      error: err => this.store.dispatch(UploadActions.uploadFailed({ id: jobId, error: err.message })),
    });
  }

  statusLabel(status: string): string {
    const labels: Record<string, string> = {
      queued: 'Na fila', uploading: 'Enviando',
      extracting: 'Extraindo', indexing: 'Indexando',
      completed: 'Concluído', failed: 'Erro',
    };
    return labels[status] ?? status;
  }
}
