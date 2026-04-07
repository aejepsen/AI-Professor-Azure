import { AfterViewInit, ChangeDetectionStrategy, ChangeDetectorRef, Component, ElementRef, NgZone, ViewChild, inject, OnDestroy, OnInit } from '@angular/core';
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
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChatComponent implements OnInit, AfterViewInit, OnDestroy {
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  private zone = inject(NgZone);
  protected auth = inject(AuthService);
  private state = inject(ChatStateService);

  get messages() { return this.state.messages; }
  query = '';
  serverStatus: 'starting' | 'ready' | 'error' = 'starting';
  warmupAttempt = 0;
  copiedIndex: number | null = null;
  private stopKeepalive?: () => void;
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef<HTMLElement>;

  ngAfterViewInit(): void {
    const el = this.messagesContainer.nativeElement;
    this.zone.runOutsideAngular(() => {
      el.addEventListener('wheel', (e: WheelEvent) => {
        e.preventDefault();
        el.scrollTop += e.deltaY;
      }, { passive: false });

    });
  }

  ngOnInit(): void {
    // Warmup e keepalive fora do Zone.js para não disparar change detection
    this.zone.runOutsideAngular(() => {
      this.api.warmup(attempt => {
        this.zone.run(() => {
          this.warmupAttempt = attempt;
          this.cdr.markForCheck();
        });
      }).then(() => {
        this.zone.run(() => {
          this.serverStatus = 'ready';
          this.cdr.markForCheck();
        });
        this.stopKeepalive = this.api.startKeepalive();
      }).catch(() => {
        this.zone.run(() => {
          this.serverStatus = 'error';
          this.cdr.markForCheck();
        });
      });
    });
  }

  ngOnDestroy(): void {
    this.stopKeepalive?.();
  }

  copy(text: string, index: number): void {
    navigator.clipboard.writeText(text).then(() => {
      this.copiedIndex = index;
      this.cdr.markForCheck();
      setTimeout(() => { this.copiedIndex = null; this.cdr.markForCheck(); }, 2000);
    });
  }

  async send() {
    if (!this.query.trim()) return;

    this.state.addMessage('user', this.query);
    const q = this.query;
    this.query = '';
    this.cdr.markForCheck();

    const token = await this.auth.getToken();
    const assistantMsg = this.state.addMessage('assistant', '');

    try {
      for await (const chunk of this.api.chat(q, token!)) {
        assistantMsg.text += chunk;
        this.state.updateHtml(assistantMsg);
        this.cdr.markForCheck();
      }
    } catch (err) {
      assistantMsg.text = 'Erro ao obter resposta.';
      this.state.updateHtml(assistantMsg);
      this.cdr.markForCheck();
    }
  }
}
