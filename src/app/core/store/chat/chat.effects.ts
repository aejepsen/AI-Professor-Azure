// src/app/core/store/chat/chat.effects.ts
import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { Store } from '@ngrx/store';
import { switchMap, map, catchError, tap } from 'rxjs/operators';
import { of, EMPTY } from 'rxjs';
import { v4 as uuid } from 'uuid';

import * as ChatActions from './chat.actions';
import { ChatService, ChatMessage } from '../../services/chat.service';
import { AppState } from '../index';

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
          id:        uuid(),
          role:      'user',
          content:   question,
          timestamp: new Date().toISOString(),
        };
        const assistantId = uuid();
        const assistantMsg: ChatMessage = {
          id:        assistantId,
          role:      'assistant',
          content:   '',
          timestamp: new Date().toISOString(),
          loading:   true,
        };

        this.store.dispatch(ChatActions.addUserMessage({ message: userMsg }));
        this.store.dispatch(ChatActions.addAssistantMessage({ message: assistantMsg }));

        // Busca histórico atual do store para enviar ao backend
        const history: { role: string; content: string }[] = [];

        return this.chatSvc.streamAnswer(question, conversationId, history).pipe(
          tap(chunk => {
            if (chunk.type === 'token') {
              this.store.dispatch(ChatActions.streamToken({
                token: chunk.text ?? '',
                messageId: assistantId,
              }));
            }
            if (chunk.type === 'sources') {
              this.store.dispatch(ChatActions.streamSources({
                sources: chunk.sources ?? [],
                messageId: assistantId,
              }));
            }
            if (chunk.type === 'done') {
              this.store.dispatch(ChatActions.streamDone({ messageId: assistantId }));
            }
            if (chunk.type === 'error') {
              this.store.dispatch(ChatActions.streamError({
                error: chunk.error ?? 'Erro desconhecido',
                messageId: assistantId,
              }));
            }
          }),
          map(() => EMPTY),
          catchError(err => {
            this.store.dispatch(ChatActions.streamError({
              error: err.message ?? 'Falha na conexão',
              messageId: assistantId,
            }));
            return EMPTY;
          }),
        );
      }),
    ),
  { dispatch: false });
}
