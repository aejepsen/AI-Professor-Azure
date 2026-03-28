// src/app/core/store/upload/upload.actions.ts
import { createAction, props } from '@ngrx/store';
import { UploadJob } from './upload.reducer';

export const startUpload = createAction(
  '[Upload] Start',
  props<{ job: UploadJob }>()
);

export const updateProgress = createAction(
  '[Upload] Update Progress',
  props<{ id: string; progress: number }>()
);

export const updateStatus = createAction(
  '[Upload] Update Status',
  props<{ id: string; status: UploadJob['status'] }>()
);

export const uploadComplete = createAction(
  '[Upload] Complete',
  props<{ id: string }>()
);

export const uploadFailed = createAction(
  '[Upload] Failed',
  props<{ id: string; error: string }>()
);

export const clearCompleted = createAction('[Upload] Clear Completed');
