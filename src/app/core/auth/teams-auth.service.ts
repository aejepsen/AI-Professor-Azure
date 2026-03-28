// src/app/core/auth/teams-auth.service.ts
import { Injectable, signal } from '@angular/core';
import { MsalService } from '@azure/msal-angular';
import { AccountInfo, SilentRequest } from '@azure/msal-browser';
import * as microsoftTeams from '@microsoft/teams-js';
import { environment } from '../../../environments/environment';

export interface UserProfile {
  id: string;
  displayName: string;
  mail: string;
  jobTitle: string;
  department: string;
  photoUrl: string;
  groups: string[];   // Entra ID group IDs — used for permission filtering
}

@Injectable({ providedIn: 'root' })
export class TeamsAuthService {
  readonly profile = signal<UserProfile | null>(null);
  readonly token   = signal<string>('');
  readonly loading = signal(false);

  constructor(private msal: MsalService) {}

  /** Silent SSO: exchanges Teams token for Entra ID access token */
  async authenticateSilently(): Promise<string> {
    this.loading.set(true);
    try {
      // Step 1: get Teams SSO token
      const teamsToken = await microsoftTeams.authentication.getAuthToken();

      // Step 2: OBO flow — exchange Teams token for API token
      // This happens server-side; the Angular app sends the Teams token to the backend
      // which performs the OBO exchange and returns an access token
      const response = await fetch(`${environment.apiUrl}/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ teams_token: teamsToken }),
      });

      const { access_token, groups } = await response.json();
      this.token.set(access_token);

      await this.loadUserProfile(access_token, groups);
      return access_token;
    } catch (err) {
      // Fallback: MSAL interactive (opens popup)
      const result = await this.msal.instance.loginPopup({
        scopes: [environment.apiScope, 'User.Read', 'GroupMember.Read.All'],
      });
      this.token.set(result.accessToken);
      return result.accessToken;
    } finally {
      this.loading.set(false);
    }
  }

  private async loadUserProfile(token: string, groups: string[]): Promise<void> {
    const headers = { Authorization: `Bearer ${token}` };
    const [meRes, photoRes] = await Promise.allSettled([
      fetch('https://graph.microsoft.com/v1.0/me', { headers }),
      fetch('https://graph.microsoft.com/v1.0/me/photo/$value', { headers }),
    ]);

    const me      = meRes.status === 'fulfilled' ? await meRes.value.json() : {};
    const photoUrl = photoRes.status === 'fulfilled' && photoRes.value.ok
      ? URL.createObjectURL(await photoRes.value.blob())
      : 'assets/default-avatar.svg';

    this.profile.set({
      id:          me.id ?? '',
      displayName: me.displayName ?? '',
      mail:        me.mail ?? '',
      jobTitle:    me.jobTitle ?? '',
      department:  me.department ?? '',
      photoUrl,
      groups,
    });
  }
}
