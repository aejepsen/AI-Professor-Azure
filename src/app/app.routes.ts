// src/app/app.routes.ts
import { Routes } from '@angular/router';
import { MsalGuard } from '@azure/msal-angular';
import { TabConfigComponent } from './tab-config/tab-config.component';
import { AuthCallbackComponent } from './core/auth/auth-callback.component';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./shell/shell.component').then(m => m.ShellComponent),
    canActivate: [MsalGuard],
    children: [
      { path: '',          redirectTo: 'chat', pathMatch: 'full' },
      { path: 'chat',      loadComponent: () => import('./chat/chat.component').then(m => m.ChatComponent) },
      { path: 'history',   loadComponent: () => import('./history/history.component').then(m => m.HistoryComponent) },
      { path: 'knowledge', loadComponent: () => import('./knowledge/knowledge.component').then(m => m.KnowledgeComponent) },
      { path: 'upload',    loadComponent: () => import('./upload/upload.component').then(m => m.UploadComponent) },
      { path: 'dashboard', loadComponent: () => import('./dashboard/dashboard.component').then(m => m.DashboardComponent) },
    ],
  },
  { path: 'config',  component: TabConfigComponent },
  { path: 'auth',    component: AuthCallbackComponent },
  { path: '**',      redirectTo: 'chat' },
];
