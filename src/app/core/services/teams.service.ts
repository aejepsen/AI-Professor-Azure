// src/app/core/services/teams.service.ts
import { Injectable } from '@angular/core';

export type TeamsTheme = 'default' | 'dark' | 'contrast';

@Injectable({ providedIn: 'root' })
export class TeamsService {
  private theme: TeamsTheme = 'default';

  getTheme(): TeamsTheme {
    return this.theme;
  }

  setTheme(theme: TeamsTheme): void {
    this.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
  }

  isInTeams(): boolean {
    return typeof (window as any).microsoftTeams !== 'undefined';
  }

  initialize(): void {
    if (this.isInTeams()) {
      try {
        const teams = (window as any).microsoftTeams;
        teams.initialize();
        teams.getContext((ctx: any) => {
          if (ctx?.theme) this.setTheme(ctx.theme as TeamsTheme);
        });
        teams.registerOnThemeChangeHandler((theme: string) => {
          this.setTheme(theme as TeamsTheme);
        });
      } catch (_) {}
    }
  }
}
