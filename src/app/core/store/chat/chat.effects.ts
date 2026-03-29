// src/app/core/store/chat/chat.effects.ts
import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { Store } from '@ngrx/store';
import { tap, switchMap, catchError } from 'rxjs/operators';
import { EMPTY } from 'rxjs';

import * as ChatActions from './chat.actions';
import { ChatService, ChatMessage } from '../../services/chat.service';
import { AppState } from '../index';

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

@Injectable()
export class ChatEffects {
  private actions$ = inject(Actions);
  private chatSvc  = inject(ChatService);
  private store    = inject(Store<AppState>);

  sendMessage$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ChatActions.sendMessage),
      switchMap(({ question, conversationId }) => {
        const userMsg: ChatMessage = {
          id: generateId(), role: 'user', content: question,
          timestamp: new Date().toISOString(),
        };
        const assistantId = generateId();
        const assistantMsg: ChatMessage = {
          id: assistantId, role: 'assistant', content: '',
          timestamp: new Date().toISOString(), loading: true,
        };

        this.store.dispatch(ChatActions.addUserMessage({ message: userMsg }));
        this.store.dispatch(ChatActions.addAssistantMessage({ message: assistantMsg }));

        return this.chatSvc.streamAnswer(question, conversationId, []).pipe(
          tap(chunk => {
            if (chunk.type === 'token') {
              this.store.dispatch(ChatActions.streamToken({ token: chunk.text ?? '', messageId: assistantId }));
            }
            if (chunk.type === 'sources') {
              this.store.dispatch(ChatActions.streamSources({ sources: chunk.sources ?? [], messageId: assistantId }));
            }
            if (chunk.type === 'done') {
              this.store.dispatch(ChatActions.streamDone({ messageId: assistantId }));
            }
            if (chunk.type === 'error') {
              this.store.dispatch(ChatActions.streamError({ error: chunk.error ?? 'Erro', messageId: assistantId }));
            }
          }),
          switchMap(() => EMPTY),
          catchError(err => {
            this.store.dispatch(ChatActions.streamError({ error: err.message ?? 'Falha', messageId: assistantId }));
            return EMPTY;
          }),
        );
      }),
    ),
  { dispatch: false });
}
