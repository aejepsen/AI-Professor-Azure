import { Injectable } from '@angular/core';

const BACKEND_URL = 'https://ai-professor-backend.bluedesert-c198f5d7.eastus.azurecontainerapps.io';

export interface IngestResult {
  status: string;
  filename: string;
  n_chunks: number;
  duration_sec?: number;
  message?: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {

  async warmup(onRetry?: (attempt: number) => void): Promise<void> {
    const MAX = 24; // 2 minutos (24 x 5s)
    for (let i = 0; i < MAX; i++) {
      try {
        const res = await fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(5000) });
        if (res.ok) return;
      } catch { /* container ainda subindo */ }
      onRetry?.(i + 1);
      await new Promise(r => setTimeout(r, 5000));
    }
    throw new Error('Servidor não respondeu após 2 minutos.');
  }

  startKeepalive(): () => void {
    const id = setInterval(() => {
      fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(5000) }).catch(() => {});
    }, 90_000); // a cada 90s — evita scale-to-zero
    return () => clearInterval(id);
  }

  async *chat(query: string, token: string): AsyncGenerator<string> {
    const res = await fetch(`${BACKEND_URL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ query }),
    });

    if (!res.ok) throw new Error(`${res.status}`);

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]') return;
        try {
          const parsed = JSON.parse(data);
          if (parsed.text) yield parsed.text;
        } catch { /* ignorar linhas malformadas */ }
      }
    }
  }

  async ingest(file: File, token: string): Promise<IngestResult> {
    const form = new FormData();
    form.append('file', file, file.name);

    const res = await fetch(`${BACKEND_URL}/ingest`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: form,
    });

    const json = await res.json();
    if (!res.ok) throw new Error(json.detail ?? `Erro ${res.status}`);
    return json as IngestResult;
  }

  async ingestViaBlob(
    file: File,
    token: string,
    onProgress: (percent: number) => void,
    onPhase: (phase: 'upload' | 'processing') => void,
  ): Promise<IngestResult> {
    // 1. Obter SAS token do backend
    const sasRes = await fetch(
      `${BACKEND_URL}/ingest/sas-token?filename=${encodeURIComponent(file.name)}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    const sasJson = await sasRes.json();
    if (!sasRes.ok) throw new Error(sasJson.detail ?? `Erro ${sasRes.status}`);
    const { upload_url, blob_name } = sasJson as { upload_url: string; blob_name: string };

    // 2. Upload direto para o Azure Blob Storage com progresso via XHR
    onPhase('upload');
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('PUT', upload_url);
      xhr.setRequestHeader('x-ms-blob-type', 'BlockBlob');
      xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');

      xhr.upload.onprogress = (ev) => {
        if (ev.lengthComputable) {
          const percent = Math.round((ev.loaded / ev.total) * 100);
          onProgress(Math.min(percent, 100));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve();
        else reject(new Error(`Upload falhou: ${xhr.status} ${xhr.statusText}`));
      };
      xhr.onerror = () => reject(new Error('Erro de rede durante o upload.'));
      xhr.send(file);
    });

    // 3. Solicitar processamento em background — retorna job_id imediatamente
    onPhase('processing');
    const processRes = await fetch(`${BACKEND_URL}/ingest/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ blob_name, original_filename: file.name }),
    });
    const processJson = await processRes.json();
    if (!processRes.ok) throw new Error(processJson.detail ?? `Erro ${processRes.status}`);

    const { job_id } = processJson as { job_id: string };

    // 4. Polling até concluir
    return this._pollJobStatus(job_id, token);
  }

  private async _pollJobStatus(jobId: string, token: string): Promise<IngestResult> {
    const INTERVAL_MS = 5000;
    const MAX_ATTEMPTS = 360; // 30 minutos

    for (let i = 0; i < MAX_ATTEMPTS; i++) {
      await new Promise((r) => setTimeout(r, INTERVAL_MS));

      const res = await fetch(`${BACKEND_URL}/ingest/status/${jobId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const json = await res.json();

      if (!res.ok) throw new Error(json.detail ?? `Erro ${res.status}`);
      if (json.status === 'done') return json as IngestResult;
      if (json.status === 'error') throw new Error(json.detail ?? 'Erro no processamento.');
      // status === 'processing' → continua polling
    }

    throw new Error('Timeout: processamento demorou mais de 30 minutos.');
  }
}
