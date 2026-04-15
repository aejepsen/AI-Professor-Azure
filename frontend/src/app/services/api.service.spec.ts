import { TestBed } from '@angular/core/testing';
import { ApiService } from './api.service';
import { vi } from 'vitest';

const BACKEND_URL = 'https://ai-professor-backend.bravebush-60555594.eastus.azurecontainerapps.io';

describe('ApiService', () => {
  let service: ApiService;
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ApiService);
    fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  // ─── chat() ────────────────────────────────────────────────────────────────

  it('chat() emits text chunks from SSE stream', async () => {
    const sseBody = 'data: {"text":"Olá"}\n\ndata: {"text":" mundo"}\n\ndata: [DONE]\n\n';
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(ctrl) {
        ctrl.enqueue(encoder.encode(sseBody));
        ctrl.close();
      },
    });
    fetchSpy.mockResolvedValue(new Response(stream, { status: 200 }));

    const chunks: string[] = [];
    for await (const chunk of service.chat('Olá', 'fake-token')) {
      chunks.push(chunk);
    }

    expect(chunks).toEqual(['Olá', ' mundo']);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BACKEND_URL}/chat/stream`,
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('chat() throws when backend returns 401', async () => {
    fetchSpy.mockResolvedValue(new Response(null, { status: 401 }));

    const gen = service.chat('test', 'bad-token');
    await expect(gen.next()).rejects.toThrow(/401/);
  });

  // ─── ingest() ──────────────────────────────────────────────────────────────

  it('ingest() returns n_chunks on success', async () => {
    fetchSpy.mockResolvedValue(new Response(
      JSON.stringify({ status: 'ok', n_chunks: 12, filename: 'aula.mp3' }),
      { status: 200 }
    ));

    const file = new File([new Uint8Array(10)], 'aula.mp3', { type: 'audio/mpeg' });
    const result = await service.ingest(file, 'fake-token');

    expect(result.n_chunks).toBe(12);
    expect(result.status).toBe('ok');
  });

  it('ingest() throws with message when backend returns 400', async () => {
    fetchSpy.mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Formato não suportado: .pdf' }),
      { status: 400 }
    ));

    const file = new File([new Uint8Array(10)], 'aula.pdf', { type: 'application/pdf' });
    await expect(service.ingest(file, 'fake-token')).rejects.toThrow(/Formato não suportado/);
  });
});
