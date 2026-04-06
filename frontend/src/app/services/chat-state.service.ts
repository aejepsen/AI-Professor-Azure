import { Injectable } from '@angular/core';

export interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
}

@Injectable({ providedIn: 'root' })
export class ChatStateService {
  messages: ChatMessage[] = [];
}
