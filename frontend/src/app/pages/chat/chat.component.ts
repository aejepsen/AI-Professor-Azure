import { ChangeDetectorRef, Component, inject, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';
import { ChatStateService } from '../../services/chat-state.service';

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
  private state = inject(ChatStateService);

  get messages() { return this.state.messages; }
  query = '';
  serverStatus: 'starting' | 'ready' | 'error' = 'starting';
  warmupAttempt = 0;
  copiedIndex: number | null = null;
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

  copy(text: string, index: number): void {
    navigator.clipboard.writeText(text).then(() => {
      this.copiedIndex = index;
      this.cdr.detectChanges();
      setTimeout(() => { this.copiedIndex = null; this.cdr.detectChanges(); }, 2000);
    });
  }

  async send() {
    if (!this.query.trim()) return;

    this.state.addMessage('user', this.query);
    const q = this.query;
    this.query = '';

    const token = await this.auth.getToken();
    const assistantMsg = this.state.addMessage('assistant', '');

    try {
      for await (const chunk of this.api.chat(q, token!)) {
        assistantMsg.text += chunk;
        this.state.updateHtml(assistantMsg);
        this.cdr.detectChanges();
      }
    } catch (err) {
      assistantMsg.text = 'Erro ao obter resposta.';
      this.state.updateHtml(assistantMsg);
    }
  }
}
