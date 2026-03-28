// src/app/core/store/upload/upload.effects.ts
import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { Store } from '@ngrx/store';
import { switchMap, map, catchError, filter, mergeMap } from 'rxjs/operators';
import { of, interval } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environments/environment';
import * as UploadActions from './upload.actions';
import { AppState } from '../index';

@Injectable()
export class UploadEffects {
  private actions$ = inject(Actions);
  private http     = inject(HttpClient);
  private store    = inject(Store<AppState>);

  pollStatus$ = createEffect(() =>
    this.actions$.pipe(
      ofType(UploadActions.startUpload),
      mergeMap(({ job }) =>
        interval(2000).pipe(
          switchMap(() =>
            this.http.get<any>(`${environment.apiUrl}/ingest/status/${job.id}`)
          ),
          map(status => {
            if (status.status === 'completed') {
              return UploadActions.uploadComplete({ id: job.id });
            }
            if (status.status === 'failed') {
              return UploadActions.uploadFailed({ id: job.id, error: status.error || 'Falha' });
            }
            return UploadActions.updateProgress({ id: job.id, progress: status.progress || 0 });
          }),
          catchError(() => of(UploadActions.uploadFailed({ id: job.id, error: 'Erro de conexão' }))),
        )
      ),
    )
  );
}
