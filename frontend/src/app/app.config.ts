import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { PublicClientApplication, LogLevel } from '@azure/msal-browser';

import { routes } from './app.routes';
import { MSAL_INSTANCE } from './services/auth.service';

const msalInstance = new PublicClientApplication({
  auth: {
    clientId: 'af303288-3f78-411c-8a64-4a2c2ec56ae0',
    authority: 'https://login.microsoftonline.com/d0900507-73c9-42c3-a8bf-a8eabdd611d8',
    redirectUri: window.location.origin,
  },
  cache: { cacheLocation: 'localStorage' },
  system: {
    loggerOptions: {
      loggerCallback: (level, msg) => {
        if (level === LogLevel.Error) console.error(msg);
      },
    },
  },
});

await msalInstance.initialize();

// Processa o redirect de volta do login Microsoft e seta a conta ativa
const redirectResult = await msalInstance.handleRedirectPromise();
if (redirectResult?.account) {
  msalInstance.setActiveAccount(redirectResult.account);
} else {
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length > 0) msalInstance.setActiveAccount(accounts[0]);
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    { provide: MSAL_INSTANCE, useValue: msalInstance },
  ],
};
