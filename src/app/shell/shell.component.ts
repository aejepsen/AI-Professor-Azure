// src/app/shell/shell.component.ts
import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, RouterOutlet } from '@angular/router';
import { TeamsAuthService } from '../core/auth/teams-auth.service';
import { TeamsService } from '../core/services/teams.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [CommonModule, RouterModule, RouterOutlet],
  template: `
    <div class="shell">
      <nav class="nav">
        <div class="nav-brand">
          <span class="nav-icon">🎓</span>
          <span class="nav-title">AI Professor</span>
        </div>
        <div class="nav-links">
          <a routerLink="/chat"      routerLinkActive="active">Chat</a>
          <a routerLink="/history"   routerLinkActive="active">Histórico</a>
          <a routerLink="/knowledge" routerLinkActive="active">Base</a>
          <a routerLink="/upload"    routerLinkActive="active">Upload</a>
          <a routerLink="/dashboard" routerLinkActive="active">Dashboard</a>
        </div>
        <div class="nav-user" *ngIf="profile()">
          <div class="avatar">{{ initials() }}</div>
          <span class="user-name">{{ profile()?.displayName }}</span>
        </div>
      </nav>
      <main class="main">
        <router-outlet />
      </main>
    </div>
  `,
  styles: [`
    .shell { display: flex; flex-direction: column; height: 100vh; background: #f8f9fa; }
    .nav { display: flex; align-items: center; gap: 24px; padding: 0 24px; height: 52px; background: #fff; border-bottom: 1px solid #e8eaed; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .nav-brand { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 16px; color: #1a73e8; }
    .nav-icon { font-size: 20px; }
    .nav-links { display: flex; gap: 4px; flex: 1; }
    .nav-links a { padding: 6px 12px; border-radius: 6px; text-decoration: none; color: #444; font-size: 14px; transition: all 0.15s; }
    .nav-links a:hover { background: #f1f3f4; color: #1a73e8; }
    .nav-links a.active { background: #e8f0fe; color: #1a73e8; font-weight: 500; }
    .nav-user { display: flex; align-items: center; gap: 8px; }
    .avatar { width: 32px; height: 32px; border-radius: 50%; background: #1a73e8; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; }
    .user-name { font-size: 13px; color: #444; }
    .main { flex: 1; overflow: auto; }
  `],
})
export class ShellComponent implements OnInit {
  private authSvc  = inject(TeamsAuthService);
  private teamsSvc = inject(TeamsService);

  profile = this.authSvc.profile;

  ngOnInit() {
    this.teamsSvc.initialize();
  }

  initials(): string {
    const name = this.profile()?.displayName ?? 'U';
    return name.split(' ').map((p: string) => p[0]).slice(0, 2).join('').toUpperCase();
  }
}
