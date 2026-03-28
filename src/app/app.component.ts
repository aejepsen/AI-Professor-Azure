// src/app/app.component.ts
import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { CommonModule } from '@angular/common';
import { TeamsService } from './core/services/teams.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, CommonModule],
  template: `
    <!-- Splash enquanto Teams SDK inicializa -->
    <div *ngIf="!ready" class="splash">
      <div class="splash-inner">
        <div class="splash-icon">🎓</div>
        <p class="splash-text">AI Professor</p>
        <div class="splash-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>

    <!-- App principal -->
    <router-outlet *ngIf="ready" />
  `,
  styles: [`
    :host { display: block; height: 100vh; }

    .splash {
      height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #0f2d5e;
    }
    .splash-inner { text-align: center; }
    .splash-icon { font-size: 56px; margin-bottom: 16px; animation: pulse 1.5s infinite; }
    .splash-text { color: white; font-size: 22px; font-weight: 700; margin: 0 0 24px; font-family: 'Segoe UI', sans-serif; }
    .splash-dots { display: flex; gap: 8px; justify-content: center; }
    .splash-dots span {
      width: 10px; height: 10px; border-radius: 50%;
      background: #0ea5e9;
      animation: bounce 1.2s infinite;
    }
    .splash-dots span:nth-child(2) { animation-delay: 0.2s; }
    .splash-dots span:nth-child(3) { animation-delay: 0.4s; }

    @keyframes pulse  { 0%,100% { opacity:1; } 50% { opacity:0.7; } }
    @keyframes bounce { 0%,60%,100% { transform:translateY(0); } 30% { transform:translateY(-8px); } }
  `],
})
export class AppComponent implements OnInit {
  private teams = inject(TeamsService);
  ready = false;

  async ngOnInit() {
    try {
      await this.teams.initialize();
    } catch (e) {
      // Fora do contexto Teams (ex: testes locais)
      console.warn('[Teams] Rodando fora do Teams — modo standalone');
    } finally {
      this.ready = true;
    }
  }
}
