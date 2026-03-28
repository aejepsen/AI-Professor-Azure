// src/app/core/interceptors/auth.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { MsalService } from '@azure/msal-angular';
import { from, switchMap } from 'rxjs';
import { environment } from '../../../environments/environment';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const msal = inject(MsalService);

  if (!req.url.startsWith(environment.apiUrl)) {
    return next(req);
  }

  const account = msal.instance.getActiveAccount()
    || msal.instance.getAllAccounts()[0];

  if (!account) {
    return next(req);
  }

  return from(
    msal.instance.acquireTokenSilent({
      scopes: [environment.apiScope],
      account,
    })
  ).pipe(
    switchMap(result => {
      const authReq = req.clone({
        setHeaders: { Authorization: `Bearer ${result.accessToken}` },
      });
      return next(authReq);
    }),
  );
};
