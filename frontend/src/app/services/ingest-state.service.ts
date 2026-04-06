import { Injectable, inject } from '@angular/core';
import { ApiService } from './api.service';
import { AuthService } from './auth.service';

const ALLOWED = ['.mkv', '.mp4', '.mp3', '.wav', '.m4a', '.webm'];

@Injectable({ providedIn: 'root' })
export class IngestStateService {
  private api = inject(ApiService);
  private auth = inject(AuthService);

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
  private _onChange?: () => void;

  /** O componente registra um callback para forçar detectChanges quando o estado mudar. */
  setChangeCallback(fn: () => void) { this._onChange = fn; }
  clearChangeCallback() { this._onChange = undefined; }

  private notify() { this._onChange?.(); }

  async startIngest(file: File): Promise<void> {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED.includes(ext)) {
      this.error = `Formato não suportado: ${ext}. Use: ${ALLOWED.join(', ')}`;
      return;
    }

    this.error = '';
    this.success = false;
    this.uploadPercent = 0;
    this.phase = 'upload';
    this.loading = true;
    this.estimatedMinutes = await this._estimateProcessingMinutes(file);
    this.notify();

    try {
      const token = await this.auth.getToken();
      const result = await this.api.ingestViaBlob(
        file,
        token!,
        (percent) => { this.uploadPercent = percent; this.notify(); },
        (phase) => {
          this.phase = phase;
          if (phase === 'processing') this._startProcessingAnimation();
          this.notify();
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
      this.notify();
    }
  }

  reset() {
    this.loading = false;
    this.success = false;
    this.error = '';
    this.nChunks = 0;
    this.filename = '';
    this.uploadPercent = 0;
    this.processingPercent = 0;
    this.estimatedMinutes = 0;
    this.phase = '';
    this._stopProcessingAnimation();
    this.notify();
  }

  private _startProcessingAnimation() {
    this.processingPercent = 0;
    this._processingStartMs = Date.now();
    const totalMs = this.estimatedMinutes * 60 * 1000 || 600_000;
    this._processingTimer = setInterval(() => {
      const elapsed = Date.now() - this._processingStartMs;
      this.processingPercent = Math.min((elapsed / totalMs) * 100, 90);
      this.notify();
    }, 1500);
  }

  private _stopProcessingAnimation() {
    if (this._processingTimer) {
      clearInterval(this._processingTimer);
      this._processingTimer = null;
    }
    this.processingPercent = 100;
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
      return Math.ceil(durationSec / 3 / 60);
    } catch {
      return 0;
    }
  }
}
