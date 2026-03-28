// src/app/core/services/teams.service.ts
import { Injectable, signal } from '@angular/core';
import * as microsoftTeams from '@microsoft/teams-js';
import {
  webLightTheme, webDarkTheme, webHighContrastTheme, setTheme
} from '@fluentui/web-components';

export interface TeamsContext {
  userId: string;
  displayName: string;
  loginHint: string;
  tenantId: string;
  theme: 'default' | 'dark' | 'contrast';
  locale: string;
  channelId?: string;
  teamId?: string;
}

@Injectable({ providedIn: 'root' })
export class TeamsService {
  readonly context   = signal<TeamsContext | null>(null);
  readonly isReady   = signal(false);
  readonly theme     = signal<'default' | 'dark' | 'contrast'>('default');

  async initialize(): Promise<void> {
    await microsoftTeams.app.initialize();

    const ctx = await microsoftTeams.app.getContext();
    this.context.set({
      userId:      ctx.user?.id ?? '',
      displayName: ctx.user?.displayName ?? '',
      loginHint:   ctx.user?.loginHint ?? '',
      tenantId:    ctx.user?.tenant?.id ?? '',
      theme:       (ctx.app.theme as any) ?? 'default',
      locale:      ctx.app.locale ?? 'pt-BR',
      channelId:   ctx.channel?.id,
      teamId:      ctx.team?.internalId,
    });

    this.applyTheme(ctx.app.theme ?? 'default');

    microsoftTeams.app.registerOnThemeChangeHandler(theme => {
      this.theme.set(theme as any);
      this.applyTheme(theme);
    });

    this.isReady.set(true);
  }

  /** Opens a video at exact timestamp in a Teams Task Module */
  openVideoAtTimestamp(videoUrl: string, timestampSeconds: number): void {
    const url = `${videoUrl}#t=${timestampSeconds}`;
    microsoftTeams.tasks.startTask({
      title: 'Trecho do Vídeo',
      url,
      width: 900,
      height: 560,
    });
  }

  /** Shows a toast notification inside Teams */
  showNotification(message: string): void {
    // Teams SDK v2 uses app.notifySuccess for config pages;
    // for general toasts, use the Angular toast service
    console.info('[Teams Notification]', message);
  }

  /** Deep link to open a file in the Teams file viewer */
  openFileDeepLink(fileUrl: string, fileName: string): void {
    const encoded = encodeURIComponent(fileUrl);
    const deepLink = `https://teams.microsoft.com/l/file/0?objectUrl=${encoded}&baseUrl=${encoded}&serviceName=&threadId=&groupId=`;
    microsoftTeams.app.openLink(deepLink);
  }

  private applyTheme(theme: string): void {
    const tokens = theme === 'dark'     ? webDarkTheme
                 : theme === 'contrast' ? webHighContrastTheme
                 : webLightTheme;
    setTheme(tokens);
    document.body.setAttribute('data-theme', theme);
  }
}
