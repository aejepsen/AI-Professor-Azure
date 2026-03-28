// src/app/core/store/upload/upload.reducer.ts
import { createReducer, on } from '@ngrx/store';
import * as UploadActions from './upload.actions';

export interface UploadJob {
  id:        string;
  filename:  string;
  status:    'queued' | 'uploading' | 'extracting' | 'indexing' | 'completed' | 'failed';
  progress:  number;
  error?:    string;
}

export interface UploadState {
  jobs: UploadJob[];
}

const initialState: UploadState = { jobs: [] };

export const uploadReducer = createReducer(
  initialState,

  on(UploadActions.startUpload, (state, { job }) => ({
    jobs: [...state.jobs, job],
  })),

  on(UploadActions.updateProgress, (state, { id, progress }) => ({
    jobs: state.jobs.map(j => j.id === id ? { ...j, progress } : j),
  })),

  on(UploadActions.updateStatus, (state, { id, status }) => ({
    jobs: state.jobs.map(j => j.id === id ? { ...j, status } : j),
  })),

  on(UploadActions.uploadComplete, (state, { id }) => ({
    jobs: state.jobs.map(j => j.id === id ? { ...j, status: 'completed' as const, progress: 100 } : j),
  })),

  on(UploadActions.uploadFailed, (state, { id, error }) => ({
    jobs: state.jobs.map(j => j.id === id ? { ...j, status: 'failed' as const, error } : j),
  })),

  on(UploadActions.clearCompleted, state => ({
    jobs: state.jobs.filter(j => j.status !== 'completed'),
  })),
);
