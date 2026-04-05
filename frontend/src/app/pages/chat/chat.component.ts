import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent {
  private api = inject(ApiService);
  protected auth = inject(AuthService);

  messages: { role: 'user' | 'assistant'; text: string }[] = [];
  query = '';

  async send() {
    if (!this.query.trim()) return;

    this.messages.push({ role: 'user', text: this.query });
    const q = this.query;
    this.query = '';

    const token = await this.auth.getToken();
    const assistantMsg = { role: 'assistant' as const, text: '' };
    this.messages.push(assistantMsg);

    for await (const chunk of this.api.chat(q, token!)) {
      assistantMsg.text += chunk;
    }
  }
}
