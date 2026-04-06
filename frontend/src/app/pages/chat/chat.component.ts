import { ChangeDetectorRef, Component, inject, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { marked } from 'marked';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  protected auth = inject(AuthService);

  messages: { role: 'user' | 'assistant'; text: string }[] = [];
  query = '';
  serverStatus: 'starting' | 'ready' | 'error' = 'starting';
  warmupAttempt = 0;
  private stopKeepalive?: () => void;

  ngOnInit(): void {
    this.api.warmup(attempt => {
      this.warmupAttempt = attempt;
      this.cdr.detectChanges();
    }).then(() => {
      this.serverStatus = 'ready';
      this.stopKeepalive = this.api.startKeepalive();
      this.cdr.detectChanges();
    }).catch(() => {
      this.serverStatus = 'error';
      this.cdr.detectChanges();
    });
  }

  ngOnDestroy(): void {
    this.stopKeepalive?.();
  }

  md(text: string): string {
    return marked.parse(text) as string;
  }

  async send() {
    if (!this.query.trim()) return;

    this.messages.push({ role: 'user', text: this.query });
    const q = this.query;
    this.query = '';

    const token = await this.auth.getToken();
    console.log('[Chat] token:', token ? token.substring(0, 30) + '...' : null);
    const assistantMsg = { role: 'assistant' as const, text: '' };
    this.messages.push(assistantMsg);

    try {
      for await (const chunk of this.api.chat(q, token!)) {
        console.log('[Chat] chunk:', chunk);
        assistantMsg.text += chunk;
        this.cdr.detectChanges();
      }
      console.log('[Chat] stream done');
    } catch (err) {
      console.error('[Chat] error:', err);
      assistantMsg.text = 'Erro ao obter resposta.';
    }
  }
}
