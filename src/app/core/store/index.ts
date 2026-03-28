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
