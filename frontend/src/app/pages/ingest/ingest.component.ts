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
  phase: 'upload' | 'processing' | '' = '';

  private _processingTimer: ReturnType<typeof setInterval> | null = null;

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

    this.loading = true;
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
    this._processingTimer = setInterval(() => {
      // Avança rápido no início, desacelera perto de 90%
      const remaining = 90 - this.processingPercent;
      this.processingPercent += remaining * 0.03;
      this.cdr.detectChanges();
    }, 1500);
  }

  private _stopProcessingAnimation() {
    if (this._processingTimer) {
      clearInterval(this._processingTimer);
      this._processingTimer = null;
    }
    this.processingPercent = 100;
  }
}
