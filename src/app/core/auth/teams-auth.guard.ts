// src/app/core/auth/teams-auth.guard.ts
import { Injectable, inject } from '@angular/core';
import { CanActivate, Router } from '@angular/router';
import { MsalService } from '@azure/msal-angular';

@Injectable({ providedIn: 'root' })
export class TeamsAuthGuard implements CanActivate {
  private msal   = inject(MsalService);
  private router = inject(Router);

  canActivate(): boolean {
    const accounts = this.msal.instance.getAllAccounts();
    if (accounts.length > 0) {
      this.msal.instance.setActiveAccount(accounts[0]);
      return true;
    }
    this.router.navigate(['/auth']);
    return false;
  }
}
