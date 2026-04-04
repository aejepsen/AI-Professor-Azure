import { ComponentFixture, TestBed } from '@angular/core/testing';
import { IngestComponent } from './ingest.component';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';
import { vi } from 'vitest';

describe('IngestComponent', () => {
  let component: IngestComponent;
  let fixture: ComponentFixture<IngestComponent>;
  let apiSpy: { ingest: ReturnType<typeof vi.fn> };
  let authSpy: { getToken: ReturnType<typeof vi.fn>; isLoggedIn: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    apiSpy = { ingest: vi.fn() };
    authSpy = {
      getToken: vi.fn().mockResolvedValue('fake-token'),
      isLoggedIn: vi.fn().mockReturnValue(true),
    };

    await TestBed.configureTestingModule({
      imports: [IngestComponent],
      providers: [
        { provide: ApiService, useValue: apiSpy },
        { provide: AuthService, useValue: authSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(IngestComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('rejects unsupported file format without calling API', async () => {
    const file = new File([new Uint8Array(10)], 'aula.pdf', { type: 'application/pdf' });
    await component.onFileSelected(file);

    expect(component.error).toContain('não suportado');
    expect(apiSpy.ingest).not.toHaveBeenCalled();
  });

  it('calls API and sets success state for valid file', async () => {
    apiSpy.ingest.mockResolvedValue({ status: 'ok', filename: 'aula.mp3', n_chunks: 10 });
    const file = new File([new Uint8Array(10)], 'aula.mp3', { type: 'audio/mpeg' });

    await component.onFileSelected(file);

    expect(apiSpy.ingest).toHaveBeenCalledWith(file, 'fake-token');
    expect(component.success).toBe(true);
    expect(component.nChunks).toBe(10);
  });

  it('shows loading state while uploading', async () => {
    let resolveIngest!: (v: any) => void;
    apiSpy.ingest.mockReturnValue(new Promise(r => resolveIngest = r));
    const file = new File([new Uint8Array(10)], 'aula.mkv', { type: 'video/x-matroska' });

    const promise = component.onFileSelected(file);
    expect(component.loading).toBe(true);

    resolveIngest({ status: 'ok', filename: 'aula.mkv', n_chunks: 5 });
    await promise;
    expect(component.loading).toBe(false);
  });
});
