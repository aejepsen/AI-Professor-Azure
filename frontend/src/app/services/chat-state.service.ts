import { Injectable } from '@angular/core';
import { marked } from 'marked';

export interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  html: string;
  sources?: string[];
}

@Injectable({ providedIn: 'root' })
export class ChatStateService {
  messages: ChatMessage[] = [];

  addMessage(role: 'user' | 'assistant', text = ''): ChatMessage {
    const msg: ChatMessage = { role, text, html: marked.parse(text) as string };
    this.messages.push(msg);
    return msg;
  }

  updateHtml(msg: ChatMessage): void {
    msg.html = marked.parse(msg.text) as string;
  }
}
