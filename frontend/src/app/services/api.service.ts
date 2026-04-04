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
}
