// src/environments/environment.example.ts
export const environment = {
  production: false,
  clientId:      'SEU_CLIENT_ID_AQUI',
  tenantId:      'SEU_TENANT_ID_AQUI',
  apiUrl:        'https://api-ai-professor.empresa.com',
  apiScope:      'api://SEU_CLIENT_ID_AQUI/access_as_user',
  teamsTabUrl:   'https://ai-professor.empresa.com',
};


// ─────────────────────────────────────────────────────────────────────────────
// src/app/core/auth/teams-auth.guard.ts
// ─────────────────────────────────────────────────────────────────────────────
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { TeamsService } from '../services/teams.service';
import { TeamsAuthService } from './teams-auth.service';

export const TeamsAuthGuard: CanActivateFn = async () => {
  const teams = inject(TeamsService);
  const auth  = inject(TeamsAuthService);

  // Initialize Teams SDK (idempotent)
  if (!teams.isReady()) {
    await teams.initialize();
  }

  // Authenticate silently
  if (!auth.token()) {
    await auth.authenticateSilently();
  }

  return !!auth.token();
};


// ─────────────────────────────────────────────────────────────────────────────
// src/app/core/interceptors/auth.interceptor.ts
// ─────────────────────────────────────────────────────────────────────────────
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { TeamsAuthService } from '../auth/teams-auth.service';
import { environment } from '../../../environments/environment';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth  = inject(TeamsAuthService);
  const token = auth.token();

  // Only add Bearer token to our own API calls
  if (token && req.url.startsWith(environment.apiUrl)) {
    const authReq = req.clone({
      headers: req.headers.set('Authorization', `Bearer ${token}`),
    });
    return next(authReq);
  }

  return next(req);
};
