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
  phase: 'upload' | 'processing' | '' = '';

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
        (percent) => {
          this.uploadPercent = percent;
          this.cdr.detectChanges();
        },
        (phase) => {
          this.phase = phase;
          this.cdr.detectChanges();
        },
      );
      this.nChunks = result.n_chunks;
      this.filename = result.filename;
      this.success = true;
    } catch (err: any) {
      this.error = err.message ?? 'Erro ao processar arquivo.';
    } finally {
      this.loading = false;
      this.phase = '';
      this.cdr.detectChanges();
    }
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    const file = event.dataTransfer?.files[0];
    if (file) this.onFileSelected(file);
  }

  onDragOver(event: DragEvent) { event.preventDefault(); }
}
