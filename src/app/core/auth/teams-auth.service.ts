import { Injectable, inject } from '@angular/core';
import { MsalService } from '@azure/msal-angular';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class TeamsAuthService {
  private msal = inject(MsalService);

  getAccount() {
    return this.msal.instance.getActiveAccount()
      || this.msal.instance.getAllAccounts()[0]
      || null;
  }

  isAuthenticated(): boolean {
    return !!this.getAccount();
  }

  getAccessToken(): Promise<string> {
    const account = this.getAccount();
    if (!account) return Promise.resolve('');
    return this.msal.instance
      .acquireTokenSilent({ scopes: [environment.apiScope], account })
      .then(r => r.accessToken)
      .catch(() => '');
  }
}
