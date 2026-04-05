import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

const ALLOWED = ['.mkv', '.mp4', '.mp3', '.wav', '.m4a', '.webm'];

@Component({
  selector: 'app-ingest',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './ingest.component.html',
  styleUrl: './ingest.component.scss',
})
export class IngestComponent {
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);

  loading = false;
  success = false;
  error = '';
  nChunks = 0;
  filename = '';
  uploadPercent = 0;
  processingPercent = 0;
  estimatedMinutes = 0;
  phase: 'upload' | 'processing' | '' = '';

  private _processingTimer: ReturnType<typeof setInterval> | null = null;
  private _processingStartMs = 0;

  async onFileSelected(file: File) {
    this.error = '';
    this.success = false;
    this.uploadPercent = 0;
    this.phase = '';

    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED.includes(ext)) {
      this.error = `Formato não suportado: ${ext}. Use: ${ALLOWED.join(', ')}`;
      return;
    }

    this.estimatedMinutes = await this._estimateProcessingMinutes(file);
    this.loading = true;
    this.phase = 'upload';
    try {
      const token = await this.auth.getToken();
      const result = await this.api.ingestViaBlob(
        file,
        token!,
        (percent) => { this.uploadPercent = percent; this.cdr.detectChanges(); },
        (phase) => {
          this.phase = phase;
          if (phase === 'processing') this._startProcessingAnimation();
          this.cdr.detectChanges();
        },
      );
      this.nChunks = result.n_chunks;
      this.filename = result.filename;
      this.success = true;
    } catch (err: any) {
      this.error = err.message ?? 'Erro ao processar arquivo.';
    } finally {
      this._stopProcessingAnimation();
      this.loading = false;
      this.phase = '';
    }
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    const file = event.dataTransfer?.files[0];
    if (file) this.onFileSelected(file);
  }

  onDragOver(event: DragEvent) { event.preventDefault(); }

  private _startProcessingAnimation() {
    this.processingPercent = 0;
    this._processingStartMs = Date.now();
    const totalMs = this.estimatedMinutes * 60 * 1000 || 600_000; // fallback 10min

    this._processingTimer = setInterval(() => {
      const elapsed = Date.now() - this._processingStartMs;
      // Progresso baseado no tempo estimado, limitado a 90%
      this.processingPercent = Math.min((elapsed / totalMs) * 100, 90);
      this.cdr.detectChanges();
    }, 1500);
  }

  private async _estimateProcessingMinutes(file: File): Promise<number> {
    try {
      const durationSec = await new Promise<number>((resolve) => {
        const el = document.createElement('video');
        el.preload = 'metadata';
        el.onloadedmetadata = () => { URL.revokeObjectURL(el.src); resolve(el.duration); };
        el.onerror = () => resolve(0);
        el.src = URL.createObjectURL(file);
      });
      // AssemblyAI universal-2 processa ~3x mais rápido que real-time
      return Math.ceil(durationSec / 3 / 60);
    } catch {
      return 0;
    }
  }

  private _stopProcessingAnimation() {
    if (this._processingTimer) {
      clearInterval(this._processingTimer);
      this._processingTimer = null;
    }
    this.processingPercent = 100;
  }
}
