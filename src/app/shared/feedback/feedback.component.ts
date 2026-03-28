// src/app/shared/feedback/feedback.component.ts
import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatService } from '../../core/services/chat.service';

@Component({
  selector: 'app-feedback',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="feedback" *ngIf="!submitted">
      <button class="btn-thumb" [class.active]="voted === true"
              (click)="vote(true)" title="Útil">👍</button>
      <button class="btn-thumb" [class.active]="voted === false"
              (click)="vote(false)" title="Não útil">👎</button>
    </div>
    <span class="thanks" *ngIf="submitted">Obrigado!</span>
  `,
  styles: [`
    .feedback { display: flex; gap: 4px; }
    .btn-thumb {
      background: none; border: none; cursor: pointer;
      padding: 4px 6px; border-radius: 4px; font-size: 14px;
      opacity: 0.5; transition: all 0.15s;
    }
    .btn-thumb:hover, .btn-thumb.active { opacity: 1; background: var(--colorNeutralBackground3, #eee); }
    .thanks { font-size: 12px; color: var(--colorNeutralForeground3, #888); }
  `],
})
export class FeedbackComponent {
  @Input()  messageId = '';
  @Output() feedbackSent = new EventEmitter<boolean>();

  private chatSvc = inject(ChatService);

  voted:     boolean | null = null;
  submitted = false;

  vote(positive: boolean) {
    this.voted = positive;
    this.chatSvc.submitFeedback(this.messageId, positive).subscribe({
      next: () => {
        this.submitted = true;
        this.feedbackSent.emit(positive);
      },
      error: () => {
        this.submitted = true; // Não bloqueia UX em caso de erro
      },
    });
  }
}
