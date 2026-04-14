import { ChangeDetectorRef, Component, inject, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { IngestStateService } from '../../services/ingest-state.service';

@Component({
  selector: 'app-ingest',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './ingest.component.html',
  styleUrl: './ingest.component.scss',
})
export class IngestComponent implements OnInit, OnDestroy {
  protected state = inject(IngestStateService);
  private cdr = inject(ChangeDetectorRef);

  isDragActive = false;

  ngOnInit() { this.state.setChangeCallback(() => this.cdr.detectChanges()); }
  ngOnDestroy() { this.state.clearChangeCallback(); }

  onFileSelected(file: File) { this.state.startIngest(file); }

  onDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragActive = false;
    const file = event.dataTransfer?.files[0];
    if (file) this.state.startIngest(file);
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    this.isDragActive = true;
  }

  onDragLeave() { this.isDragActive = false; }
}
