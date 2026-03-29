// src/app/core/auth/teams-auth.service.ts
import { Injectable, inject, signal } from '@angular/core';
import { MsalService } from '@azure/msal-angular';
import { environment } from '../../../environments/environment';

export interface UserProfile {
  displayName: string;
  email: string;
  id: string;
}

@Injectable({ providedIn: 'root' })
export class TeamsAuthService {
  private msal = inject(MsalService);

  profile = signal<UserProfile | null>(this.buildProfile());

  private buildProfile(): UserProfile | null {
    const account = this.msal.instance.getActiveAccount()
      || this.msal.instance.getAllAccounts()[0];
    if (!account) return null;
    return {
      displayName: account.name || account.username || 'User',
      email: account.username || '',
      id: account.localAccountId || '',
    };
  }

  getAccount() {
    return this.msal.instance.getActiveAccount()
      || this.msal.instance.getAllAccounts()[0]
      || null;
  }

  isAuthenticated(): boolean {
    return !!this.getAccount();
  }

  async getAccessToken(): Promise<string> {
    const account = this.getAccount();
    if (!account) return '';
    try {
      const result = await this.msal.instance.acquireTokenSilent({
        scopes: [environment.apiScope],
        account,
      });
      this.profile.set({
        displayName: account.name || account.username || 'User',
        email: account.username || '',
        id: account.localAccountId || '',
      });
      return result.accessToken;
    } catch {
      return '';
    }
  }

  logout(): void {
    this.msal.instance.logoutRedirect();
  }
}
