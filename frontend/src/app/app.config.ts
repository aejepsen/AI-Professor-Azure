import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { PublicClientApplication, LogLevel } from '@azure/msal-browser';

import { routes } from './app.routes';
import { MSAL_INSTANCE } from './services/auth.service';

const msalInstance = new PublicClientApplication({
  auth: {
    clientId: '00000000-0000-0000-0000-000000000000', // substituir pelo App Registration ID
    authority: 'https://login.microsoftonline.com/common',
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
