import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { PublicClientApplication, LogLevel } from '@azure/msal-browser';

import { routes } from './app.routes';
import { MSAL_INSTANCE } from './services/auth.service';

const msalInstance = new PublicClientApplication({
  auth: {
    clientId: 'b0e2678a-fc0a-4fe5-81bb-f2cb1221e4d0',
    authority: 'https://login.microsoftonline.com/d0900507-73c9-42c3-a8bf-a8eabdd611d8',
    redirectUri: window.location.origin,
  },
  cache: { cacheLocation: 'sessionStorage' },
  system: {
    loggerOptions: {
      loggerCallback: (level, msg) => {
        if (level === LogLevel.Error) console.error(msg);
      },
    },
  },
});

await msalInstance.initialize();
await msalInstance.handleRedirectPromise();

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    { provide: MSAL_INSTANCE, useValue: msalInstance },
  ],
};
