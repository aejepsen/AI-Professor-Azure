import {
  AfterViewInit,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  NgZone,
  ViewChild,
  inject,
  OnInit,
} from '@angular/core';
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
export class ChatComponent implements OnInit, AfterViewInit {
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
  isStreaming = false;

  @ViewChild('messagesContainer') private messagesContainer!: ElementRef<HTMLElement>;
  @ViewChild('queryInput') private queryInput!: ElementRef<HTMLTextAreaElement>;

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
      }).catch(() => {
        this.zone.run(() => {
          this.serverStatus = 'error';
          this.cdr.markForCheck();
        });
      });
    });
  }

  onInput(event: Event): void {
    const el = event.target as HTMLTextAreaElement;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }

  copy(text: string, index: number): void {
    navigator.clipboard.writeText(text).then(() => {
      this.copiedIndex = index;
      this.cdr.markForCheck();
      setTimeout(() => { this.copiedIndex = null; this.cdr.markForCheck(); }, 2000);
    });
  }

  private isNearBottom(): boolean {
    const el = this.messagesContainer?.nativeElement;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  }

  private scrollToBottom(): void {
    if (!this.messagesContainer) return;
    requestAnimationFrame(() => {
      const el = this.messagesContainer.nativeElement;
      el.scrollTop = el.scrollHeight;
    });
  }

  private resetTextarea(): void {
    if (this.queryInput) {
      this.queryInput.nativeElement.style.height = 'auto';
    }
  }

  async send() {
    if (!this.query.trim() || this.isStreaming) return;

    this.state.addMessage('user', this.query);
    const q = this.query;
    this.query = '';
    this.resetTextarea();
    this.isStreaming = true;
    this.cdr.markForCheck();
    this.scrollToBottom();

    const token = await this.auth.getToken();
    const assistantMsg = this.state.addMessage('assistant', '');

    try {
      for await (const event of this.api.chat(q, token!)) {
        if ('text' in event) {
          assistantMsg.text += event.text;
          this.state.updateHtml(assistantMsg);
          const wasNearBottom = this.isNearBottom();
          this.cdr.markForCheck();
          if (wasNearBottom) this.scrollToBottom();
        } else if ('sources' in event) {
          assistantMsg.sources = event.sources;
          this.cdr.markForCheck();
        } else if ('error' in event) {
          assistantMsg.text = event.error;
          this.state.updateHtml(assistantMsg);
          this.cdr.markForCheck();
        }
      }
    } catch (err) {
      assistantMsg.text = 'Erro ao obter resposta.';
      this.state.updateHtml(assistantMsg);
      this.cdr.markForCheck();
    } finally {
      this.isStreaming = false;
      this.cdr.markForCheck();
    }
  }
}
