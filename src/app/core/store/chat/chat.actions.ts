// src/app/core/store/chat/chat.actions.ts
import { createAction, props } from '@ngrx/store';
import { ChatMessage, Source } from '../../services/chat.service';

export const sendMessage = createAction(
  '[Chat] Send Message',
  props<{ question: string; conversationId: string }>()
);

export const streamToken = createAction(
  '[Chat] Stream Token',
  props<{ token: string; messageId: string }>()
);

export const streamDone = createAction(
  '[Chat] Stream Done',
  props<{ messageId: string }>()
);

export const streamSources = createAction(
  '[Chat] Stream Sources',
  props<{ sources: Source[]; messageId: string }>()
);

export const streamError = createAction(
  '[Chat] Stream Error',
  props<{ error: string; messageId: string }>()
);

export const addUserMessage = createAction(
  '[Chat] Add User Message',
  props<{ message: ChatMessage }>()
);

export const addAssistantMessage = createAction(
  '[Chat] Add Assistant Message',
  props<{ message: ChatMessage }>()
);

export const clearHistory = createAction('[Chat] Clear History');

export const loadConversation = createAction(
  '[Chat] Load Conversation',
  props<{ conversationId: string }>()
);

export const loadConversationSuccess = createAction(
  '[Chat] Load Conversation Success',
  props<{ messages: ChatMessage[] }>()
);
