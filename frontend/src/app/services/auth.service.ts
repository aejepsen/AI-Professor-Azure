import { Injectable, Inject } from '@angular/core';
import { IPublicClientApplication, SilentRequest } from '@azure/msal-browser';

export const MSAL_INSTANCE = 'MSAL_INSTANCE';

const TOKEN_SCOPES = ['api://ai-professor/Chat.Read'];

@Injectable({ providedIn: 'root' })
export class AuthService {
  constructor(@Inject(MSAL_INSTANCE) private msal: IPublicClientApplication) {}

  isLoggedIn(): boolean {
    return this.msal.getAllAccounts().length > 0;
  }

  login(): void {
    this.msal.loginRedirect({ scopes: TOKEN_SCOPES });
  }

  logout(): void {
    this.msal.logoutRedirect();
  }

  async getToken(): Promise<string | null> {
    const accounts = this.msal.getAllAccounts();
    if (accounts.length === 0) return null;

    const request: SilentRequest = { scopes: TOKEN_SCOPES, account: accounts[0] };
    const result = await this.msal.acquireTokenSilent(request);
    return result.accessToken;
  }
}
