// src/app/core/auth/auth-callback.component.ts
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MsalService } from '@azure/msal-angular';

@Component({
  selector: 'app-auth-callback',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div style="display:flex;align-items:center;justify-content:center;height:100vh;
                font-family:sans-serif;color:#666;">
      <p>Autenticando...</p>
    </div>
  `,
})
export class AuthCallbackComponent implements OnInit {
  private msal   = inject(MsalService);
  private router = inject(Router);

  async ngOnInit() {
    try {
      await this.msal.instance.handleRedirectPromise();
      const accounts = this.msal.instance.getAllAccounts();
      if (accounts.length > 0) {
        this.msal.instance.setActiveAccount(accounts[0]);
      }
    } catch (e) {
      console.error('Auth callback error:', e);
    }
    this.router.navigate(['/']);
  }
}
