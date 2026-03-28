// src/app/core/store/chat/chat.reducer.ts
import { createReducer, on } from '@ngrx/store';
import { ChatMessage } from '../../services/chat.service';
import * as ChatActions from './chat.actions';

export interface ChatState {
  messages:       ChatMessage[];
  loading:        boolean;
  error:          string | null;
  conversationId: string;
}

const initialState: ChatState = {
  messages:       [],
  loading:        false,
  error:          null,
  conversationId: crypto.randomUUID(),
};

export const chatReducer = createReducer(
  initialState,

  on(ChatActions.sendMessage, (state, { question, conversationId }) => ({
    ...state,
    loading: true,
    error: null,
  })),

  on(ChatActions.addUserMessage, (state, { message }) => ({
    ...state,
    messages: [...state.messages, message],
  })),

  on(ChatActions.addAssistantMessage, (state, { message }) => ({
    ...state,
    messages: [...state.messages, message],
    loading: true,
  })),

  on(ChatActions.streamToken, (state, { token, messageId }) => ({
    ...state,
    messages: state.messages.map(m =>
      m.id === messageId
        ? { ...m, content: m.content + token, loading: true }
        : m
    ),
  })),

  on(ChatActions.streamSources, (state, { sources, messageId }) => ({
    ...state,
    messages: state.messages.map(m =>
      m.id === messageId ? { ...m, sources } : m
    ),
  })),

  on(ChatActions.streamDone, (state, { messageId }) => ({
    ...state,
    loading: false,
    messages: state.messages.map(m =>
      m.id === messageId ? { ...m, loading: false } : m
    ),
  })),

  on(ChatActions.streamError, (state, { error, messageId }) => ({
    ...state,
    loading: false,
    messages: state.messages.map(m =>
      m.id === messageId ? { ...m, loading: false, error } : m
    ),
  })),

  on(ChatActions.clearHistory, state => ({
    ...state,
    messages: [],
    conversationId: crypto.randomUUID(),
    error: null,
  })),

  on(ChatActions.loadConversationSuccess, (state, { messages }) => ({
    ...state,
    messages,
    loading: false,
  })),
);
