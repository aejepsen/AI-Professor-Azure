// src/app/app.config.ts
import { ApplicationConfig, importProvidersFrom } from '@angular/core';
import { provideRouter, withViewTransitions } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimations } from '@angular/platform-browser/animations';
import { provideStore } from '@ngrx/store';
import { provideEffects } from '@ngrx/effects';
import { provideStoreDevtools } from '@ngrx/store-devtools';
import {
  MsalModule, MsalInterceptor,
  MSAL_INSTANCE, MSAL_INTERCEPTOR_CONFIG,
  MsalService, MsalGuard, MsalBroadcastService
} from '@azure/msal-angular';
import {
  PublicClientApplication, InteractionType, BrowserCacheLocation
} from '@azure/msal-browser';

import { routes } from './app.routes';
import { environment } from '../environments/environment';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { reducers, metaReducers } from './core/store';
import { ChatEffects } from './core/store/chat/chat.effects';
import { UploadEffects } from './core/store/upload/upload.effects';

export function MSALInstanceFactory() {
  return new PublicClientApplication({
    auth: {
      clientId: environment.clientId,
      authority: `https://login.microsoftonline.com/${environment.tenantId}`,
      redirectUri: window.location.origin + '/auth',
      postLogoutRedirectUri: window.location.origin,
    },
    cache: {
      cacheLocation: BrowserCacheLocation.SessionStorage,
      storeAuthStateInCookie: false,
    },
  });
}

export function MSALInterceptorConfigFactory() {
  return {
    interactionType: InteractionType.Silent,
    protectedResourceMap: new Map([
      [`${environment.apiUrl}/*`, [environment.apiScope]],
      ['https://graph.microsoft.com/v1.0/me', ['User.Read']],
    ]),
  };
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes, withViewTransitions()),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideAnimations(),
    provideStore(reducers, { metaReducers }),
    provideEffects([ChatEffects, UploadEffects]),
    provideStoreDevtools({ maxAge: 25, logOnly: !environment.production }),

    // MSAL
    { provide: MSAL_INSTANCE, useFactory: MSALInstanceFactory },
    { provide: MSAL_INTERCEPTOR_CONFIG, useFactory: MSALInterceptorConfigFactory },
    MsalService,
    MsalGuard,
    MsalBroadcastService,
  ],
};
