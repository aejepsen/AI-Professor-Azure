// src/app/shell/shell.component.ts
import { Component, inject, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, RouterLink, RouterLinkActive } from '@angular/router';
import { TeamsService } from '../core/services/teams.service';
import { TeamsAuthService } from '../core/auth/teams-auth.service';

interface NavItem {
  path: string;
  icon: string;
  label: string;
}

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [CommonModule, RouterModule, RouterLink, RouterLinkActive],
  template: `
    <div class="shell" [attr.data-theme]="teams.theme()">

      <!-- ── Sidebar ── -->
      <nav class="sidebar">
        <div class="brand">
          <span class="brand-icon">🎓</span>
          <span class="brand-name">AI Professor</span>
        </div>

        <ul class="nav-list">
          <li *ngFor="let item of navItems">
            <a [routerLink]="item.path"
               routerLinkActive="active"
               [routerLinkActiveOptions]="{ exact: item.path === 'chat' }"
               class="nav-item">
              <span class="nav-icon">{{ item.icon }}</span>
              <span class="nav-label">{{ item.label }}</span>
            </a>
          </li>
        </ul>

        <div class="user-info" *ngIf="profile()">
          <img *ngIf="profile()?.photoUrl" [src]="profile()!.photoUrl" class="user-photo" alt="">
          <span *ngIf="!profile()?.photoUrl" class="user-initials">{{ initials() }}</span>
          <div class="user-details">
            <span class="user-name">{{ profile()?.displayName }}</span>
            <span class="user-dept">{{ profile()?.department }}</span>
          </div>
        </div>
      </nav>

      <!-- ── Main Content ── -->
      <main class="main-content">
        <router-outlet></router-outlet>
      </main>

    </div>
  `,
  styles: [`
    .shell { display: flex; height: 100vh; overflow: hidden; background: var(--colorNeutralBackground1); }

    /* Sidebar */
    .sidebar { width: 220px; display: flex; flex-direction: column; background: var(--colorNeutralBackground2); border-right: 1px solid var(--colorNeutralStroke2); flex-shrink: 0; }
    .brand { display: flex; align-items: center; gap: 10px; padding: 16px; border-bottom: 1px solid var(--colorNeutralStroke2); }
    .brand-icon { font-size: 24px; }
    .brand-name { font-size: 15px; font-weight: 700; color: var(--colorNeutralForeground1); }

    .nav-list { list-style: none; padding: 8px; margin: 0; flex: 1; display: flex; flex-direction: column; gap: 2px; }
    .nav-item { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 6px; text-decoration: none; color: var(--colorNeutralForeground2); font-size: 14px; transition: all 0.12s; }
    .nav-item:hover { background: var(--colorNeutralBackground4); color: var(--colorNeutralForeground1); }
    .nav-item.active { background: var(--colorBrandBackground2); color: var(--colorBrandForeground1); font-weight: 600; }
    .nav-icon { font-size: 18px; width: 22px; text-align: center; }

    .user-info { display: flex; align-items: center; gap: 10px; padding: 14px; border-top: 1px solid var(--colorNeutralStroke2); }
    .user-photo { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
    .user-initials { width: 32px; height: 32px; border-radius: 50%; background: var(--colorBrandBackground); color: white; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; }
    .user-details { display: flex; flex-direction: column; min-width: 0; }
    .user-name { font-size: 13px; font-weight: 600; color: var(--colorNeutralForeground1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .user-dept { font-size: 11px; color: var(--colorNeutralForeground3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    /* Main */
    .main-content { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
  `],
})
export class ShellComponent {
  readonly teams   = inject(TeamsService);
  private authSvc  = inject(TeamsAuthService);

  profile  = this.authSvc.profile;
  initials = computed(() => {
    const name = this.profile()?.displayName ?? '';
    return name.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase();
  });

  navItems: NavItem[] = [
    { path: 'chat',      icon: '💬', label: 'Chat' },
    { path: 'history',   icon: '🕐', label: 'Histórico' },
    { path: 'knowledge', icon: '📚', label: 'Base de Conhecimento' },
    { path: 'upload',    icon: '📤', label: 'Upload' },
    { path: 'dashboard', icon: '📊', label: 'Dashboard' },
  ];
}


// ─────────────────────────────────────────────────────────────────────────────
// src/styles.scss — global styles with Fluent UI tokens
// ─────────────────────────────────────────────────────────────────────────────
// @use '@fluentui/web-components/styles' as fluent;   // import in angular.json

/* Reset */
*, *::before, *::after { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
}

/* Fluent UI light theme (default) */
body[data-theme='default'] {
  --colorNeutralBackground1:       #ffffff;
  --colorNeutralBackground2:       #f5f5f5;
  --colorNeutralBackground3:       #efefef;
  --colorNeutralBackground4:       #e0e0e0;
  --colorNeutralForeground1:       #242424;
  --colorNeutralForeground2:       #424242;
  --colorNeutralForeground3:       #616161;
  --colorNeutralForeground4:       #9e9e9e;
  --colorNeutralForegroundOnBrand: #ffffff;
  --colorNeutralStroke1:           #d1d1d1;
  --colorNeutralStroke2:           #e0e0e0;
  --colorBrandBackground:          #0f6cbd;
  --colorBrandBackground2:         #cfe4fa;
  --colorBrandBackground2Hover:    #b7d9f8;
  --colorBrandBackgroundHover:     #115ea3;
  --colorBrandForeground1:         #0f6cbd;
  --colorBrandStroke1:             #0f6cbd;
}

/* Fluent UI dark theme */
body[data-theme='dark'] {
  --colorNeutralBackground1:       #1a1a1a;
  --colorNeutralBackground2:       #242424;
  --colorNeutralBackground3:       #2e2e2e;
  --colorNeutralBackground4:       #383838;
  --colorNeutralForeground1:       #f0f0f0;
  --colorNeutralForeground2:       #d0d0d0;
  --colorNeutralForeground3:       #a0a0a0;
  --colorNeutralForeground4:       #707070;
  --colorNeutralForegroundOnBrand: #ffffff;
  --colorNeutralStroke1:           #404040;
  --colorNeutralStroke2:           #363636;
  --colorBrandBackground:          #479ef5;
  --colorBrandBackground2:         #0c3b5e;
  --colorBrandBackground2Hover:    #0d4f7d;
  --colorBrandBackgroundHover:     #62abf5;
  --colorBrandForeground1:         #479ef5;
  --colorBrandStroke1:             #479ef5;
}
