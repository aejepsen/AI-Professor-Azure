import { Injectable } from '@angular/core';
import { BlockBlobClient } from '@azure/storage-blob';

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
  ): Promise<IngestResult> {
    // 1. Obter SAS token do backend
    const sasRes = await fetch(
      `${BACKEND_URL}/ingest/sas-token?filename=${encodeURIComponent(file.name)}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    const sasJson = await sasRes.json();
    if (!sasRes.ok) throw new Error(sasJson.detail ?? `Erro ${sasRes.status}`);
    const { upload_url, blob_name } = sasJson as { upload_url: string; blob_name: string };

    // 2. Upload direto para o Azure Blob Storage com progresso
    const blobClient = new BlockBlobClient(upload_url);
    await blobClient.uploadData(file, {
      onProgress: (ev) => {
        const percent = Math.round((ev.loadedBytes / file.size) * 100);
        onProgress(Math.min(percent, 99));
      },
      blobHTTPHeaders: { blobContentType: file.type || 'application/octet-stream' },
    });

    onProgress(99);

    // 3. Solicitar processamento ao backend
    const processRes = await fetch(`${BACKEND_URL}/ingest/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ blob_name, original_filename: file.name }),
    });
    const processJson = await processRes.json();
    if (!processRes.ok) throw new Error(processJson.detail ?? `Erro ${processRes.status}`);

    onProgress(100);
    return processJson as IngestResult;
  }
}
