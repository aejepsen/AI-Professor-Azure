// src/app/core/store/index.ts
import { ActionReducerMap, MetaReducer } from '@ngrx/store';
import { chatReducer, ChatState } from './chat/chat.reducer';
import { uploadReducer, UploadState } from './upload/upload.reducer';

export interface AppState {
  chat:   ChatState;
  upload: UploadState;
}

export const reducers: ActionReducerMap<AppState> = {
  chat:   chatReducer,
  upload: uploadReducer,
};

export const metaReducers: MetaReducer<AppState>[] = [];


// ─────────────────────────────────────────────────────────────────────────────
// src/app/core/store/chat/chat.actions.ts
// ─────────────────────────────────────────────────────────────────────────────
import { createAction, props } from '@ngrx/store';
import { ChatMessage } from '../../services/chat.service';

export const sendMessage = createAction(
  '[Chat] Send Message',
  props<{ question: string; conversationId: string }>()
);

export const streamToken = createAction(
  '[Chat] Stream Token',
  props<{ token: string; messageId: string }>()
);

export const streamComplete = createAction(
  '[Chat] Stream Complete',
  props<{ messageId: string }>()
);

export const streamError = createAction(
  '[Chat] Stream Error',
  props<{ messageId: string; error: string }>()
);

export const setConversation = createAction(
  '[Chat] Set Conversation',
  props<{ conversationId: string; messages: ChatMessage[] }>()
);

export const clearConversation = createAction('[Chat] Clear Conversation');

export const setFeedback = createAction(
  '[Chat] Set Feedback',
  props<{ messageId: string; positive: boolean }>()
);


// ─────────────────────────────────────────────────────────────────────────────
// src/app/core/store/chat/chat.reducer.ts
// ─────────────────────────────────────────────────────────────────────────────
import { createReducer, on } from '@ngrx/store';
import * as ChatActions from './chat.actions';
import { ChatMessage } from '../../services/chat.service';

export interface ChatState {
  conversationId:   string;
  messages:         ChatMessage[];
  streamingId:      string | null;
  loading:          boolean;
  error:            string | null;
}

const initialState: ChatState = {
  conversationId: crypto.randomUUID(),
  messages:       [],
  streamingId:    null,
  loading:        false,
  error:          null,
};

export const chatReducer = createReducer(
  initialState,

  on(ChatActions.sendMessage, (state, { question, conversationId }) => ({
    ...state,
    loading: true,
    error:   null,
    messages: [
      ...state.messages,
      {
        id:        crypto.randomUUID(),
        role:      'user' as const,
        content:   question,
        sources:   [],
        timestamp: new Date(),
      },
      {
        id:        crypto.randomUUID(),
        role:      'assistant' as const,
        content:   '',
        sources:   [],
        timestamp: new Date(),
      },
    ],
  })),

  on(ChatActions.streamToken, (state, { token, messageId }) => ({
    ...state,
    streamingId: messageId,
    messages: state.messages.map(m =>
      m.id === messageId ? { ...m, content: m.content + token } : m
    ),
  })),

  on(ChatActions.streamComplete, (state, { messageId }) => ({
    ...state,
    streamingId: null,
    loading:     false,
    messages: state.messages.map(m =>
      m.id === messageId ? { ...m } : m
    ),
  })),

  on(ChatActions.streamError, (state, { messageId, error }) => ({
    ...state,
    streamingId: null,
    loading:     false,
    error,
    messages: state.messages.map(m =>
      m.id === messageId ? { ...m, content: error } : m
    ),
  })),

  on(ChatActions.setConversation, (state, { conversationId, messages }) => ({
    ...state,
    conversationId,
    messages,
  })),

  on(ChatActions.clearConversation, state => ({
    ...state,
    conversationId: crypto.randomUUID(),
    messages:       [],
    streamingId:    null,
    error:          null,
  })),
);


// ─────────────────────────────────────────────────────────────────────────────
// src/app/core/store/chat/chat.effects.ts
// ─────────────────────────────────────────────────────────────────────────────
import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { Store } from '@ngrx/store';
import { switchMap, map, catchError } from 'rxjs/operators';
import { of, EMPTY } from 'rxjs';
import * as ChatActions from './chat.actions';
import { ChatService } from '../../services/chat.service';
import { AppState } from '../index';

@Injectable()
export class ChatEffects {
  private actions$ = inject(Actions);
  private chatSvc  = inject(ChatService);
  private store    = inject(Store<AppState>);

  streamAnswer$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ChatActions.sendMessage),
      switchMap(({ question, conversationId }) => {
        const assistantId = crypto.randomUUID();
        return this.chatSvc.streamAnswer(question, conversationId, []).pipe(
          map(chunk => {
            if (chunk.type === 'token')   return ChatActions.streamToken({ token: chunk.text ?? '', messageId: assistantId });
            if (chunk.type === 'done')    return ChatActions.streamComplete({ messageId: assistantId });
            if (chunk.type === 'error')   return ChatActions.streamError({ messageId: assistantId, error: chunk.error ?? 'Erro' });
            return ChatActions.streamComplete({ messageId: assistantId });
          }),
          catchError(err => of(ChatActions.streamError({ messageId: assistantId, error: err.message })))
        );
      })
    )
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// src/app/core/store/upload/upload.reducer.ts
// ─────────────────────────────────────────────────────────────────────────────
import { createReducer, on } from '@ngrx/store';
import { createAction, props } from '@ngrx/store';

// Actions
export const uploadStarted  = createAction('[Upload] Started',  props<{ id: string; fileName: string; fileSize: number }>());
export const uploadProgress = createAction('[Upload] Progress', props<{ id: string; progress: number }>());
export const uploadDone     = createAction('[Upload] Done',     props<{ id: string }>());
export const uploadError    = createAction('[Upload] Error',    props<{ id: string; error: string }>());
export const processingDone = createAction('[Upload] Processing Done', props<{ id: string }>());

export interface UploadJob {
  id: string; fileName: string; fileSize: number;
  status: 'uploading' | 'processing' | 'ready' | 'error';
  progress: number; error?: string;
}

export interface UploadState { jobs: UploadJob[]; }
const initialState: UploadState = { jobs: [] };

export const uploadReducer = createReducer(
  initialState,
  on(uploadStarted,  (s, a) => ({ jobs: [...s.jobs, { id: a.id, fileName: a.fileName, fileSize: a.fileSize, status: 'uploading' as const, progress: 0 }] })),
  on(uploadProgress, (s, a) => ({ jobs: s.jobs.map(j => j.id === a.id ? { ...j, progress: a.progress } : j) })),
  on(uploadDone,     (s, a) => ({ jobs: s.jobs.map(j => j.id === a.id ? { ...j, status: 'processing' as const, progress: 100 } : j) })),
  on(uploadError,    (s, a) => ({ jobs: s.jobs.map(j => j.id === a.id ? { ...j, status: 'error' as const, error: a.error } : j) })),
  on(processingDone, (s, a) => ({ jobs: s.jobs.map(j => j.id === a.id ? { ...j, status: 'ready' as const } : j) })),
);


// ─────────────────────────────────────────────────────────────────────────────
// src/app/core/store/upload/upload.effects.ts
// ─────────────────────────────────────────────────────────────────────────────
import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { HttpClient, HttpEventType } from '@angular/common/http';
import { switchMap, map, catchError, filter, mergeMap } from 'rxjs/operators';
import { of, interval } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { environment } from '../../../../environments/environment';

@Injectable()
export class UploadEffects {
  private actions$ = inject(Actions);
  private http     = inject(HttpClient);

  upload$ = createEffect(() =>
    this.actions$.pipe(
      ofType(uploadStarted),
      mergeMap(action => {
        // Actual upload handled in component via HttpClient directly
        // Effects here can handle polling for processing status
        return of(uploadProgress({ id: action.id, progress: 0 }));
      })
    )
  );
}
