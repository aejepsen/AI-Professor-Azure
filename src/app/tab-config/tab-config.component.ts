// src/app/tab-config/tab-config.component.ts
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';

declare const microsoftTeams: any;

@Component({
  selector: 'app-tab-config',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div style="padding:24px;font-family:sans-serif;">
      <h2>Configuração do AI Professor</h2>
      <p>Clique em Salvar para adicionar o AI Professor ao seu canal.</p>
    </div>
  `,
})
export class TabConfigComponent implements OnInit {
  ngOnInit() {
    try {
      microsoftTeams.initialize();
      microsoftTeams.settings.registerOnSaveHandler((saveEvent: any) => {
        microsoftTeams.settings.setSettings({
          entityId: 'ai-professor',
          contentUrl: `${window.location.origin}/`,
          suggestedDisplayName: 'AI Professor',
        });
        saveEvent.notifySuccess();
      });
      microsoftTeams.settings.setValidityState(true);
    } catch (_) {
      // Fora do Teams — modo desenvolvimento
    }
  }
}
