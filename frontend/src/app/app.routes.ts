import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'chat', pathMatch: 'full' },
  {
    path: 'chat',
    loadComponent: () =>
      import('./pages/chat/chat.component').then(m => m.ChatComponent),
  },
  {
    path: 'ingest',
    loadComponent: () =>
      import('./pages/ingest/ingest.component').then(m => m.IngestComponent),
  },
];
