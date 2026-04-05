import { Injectable, Inject } from '@angular/core';
import { IPublicClientApplication, SilentRequest } from '@azure/msal-browser';

export const MSAL_INSTANCE = 'MSAL_INSTANCE';

const TOKEN_SCOPES = ['api://087f139e-7252-49cf-ab70-abb64eac8667/access_as_user'];

@Injectable({ providedIn: 'root' })
export class AuthService {
  constructor(@Inject(MSAL_INSTANCE) private msal: IPublicClientApplication) {}

  isLoggedIn(): boolean {
    return this.msal.getAllAccounts().length > 0;
  }

  login(): void {
    this.msal.loginRedirect({ scopes: TOKEN_SCOPES }).catch(err => console.error('[MSAL] loginRedirect error:', err));
  }

  logout(): void {
    this.msal.logoutRedirect();
  }

  async getToken(): Promise<string | null> {
    const account = this.msal.getActiveAccount() ?? this.msal.getAllAccounts()[0];
    if (!account) return null;

    const request: SilentRequest = { scopes: TOKEN_SCOPES, account };
    const result = await this.msal.acquireTokenSilent(request);
    return result.accessToken;
  }
}
