// frontend/tests/e2e/chat.spec.ts
/**
 * Testes E2E com Playwright para o Angular Teams Tab App.
 * Simula o fluxo completo do usuário sem o wrapper do Teams.
 */

import { test, expect, Page } from '@playwright/test';

const BASE_URL = process.env['BASE_URL'] || 'http://localhost:4200';

// ─── Setup ────────────────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  // Injeta mock do Teams SDK para testes fora do Teams
  await page.addInitScript(() => {
    (window as any).microsoftTeams = {
      app: {
        initialize:                  () => Promise.resolve(),
        getContext:                  () => Promise.resolve({
          user:    { id: 'test-user-001', displayName: 'Test User', loginHint: 'test@empresa.com', tenant: { id: 'tenant-001' } },
          app:     { theme: 'default', locale: 'pt-BR' },
          channel: undefined,
          team:    undefined,
        }),
        registerOnThemeChangeHandler: () => {},
        openLink:                    () => {},
      },
      authentication: {
        getAuthToken: () => Promise.resolve('mock-teams-token'),
      },
      tasks: {
        startTask: () => {},
      },
    };
  });

  // Mock do endpoint de auth/token
  await page.route('**/auth/token', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      access_token: 'mock-access-token',
      groups:       ['grupo-rh', 'grupo-todos'],
      expires_in:   3600,
    }),
  }));

  await page.goto(`${BASE_URL}/chat`);
  await page.waitForLoadState('networkidle');
});

// ─── Chat ────────────────────────────────────────────────────────────────────

test.describe('Chat Component', () => {

  test('exibe estado vazio com sugestões de perguntas', async ({ page }) => {
    const emptyState = page.locator('.empty-state');
    await expect(emptyState).toBeVisible();
    await expect(emptyState.locator('h2')).toContainText('Como posso ajudar?');

    const chips = page.locator('.suggestion-chip');
    await expect(chips).toHaveCount(4);
  });

  test('envia pergunta e exibe resposta com streaming', async ({ page }) => {
    // Mock do SSE stream
    await page.route('**/chat/stream', async route => {
      const chunks = [
        'data: {"type":"token","text":"Para "}\n\n',
        'data: {"type":"token","text":"abrir um chamado "}\n\n',
        'data: {"type":"token","text":"de TI, acesse o portal."}\n\n',
        'data: {"type":"sources","sources":[{"id":"1","type":"document","name":"Manual TI.pdf","url":"https://blob/ti.pdf","page":3,"sensitivity_label":"internal","relevance_score":0.92}]}\n\n',
        'data: {"type":"done"}\n\n',
      ];
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
        body: chunks.join(''),
      });
    });

    const input = page.locator('.question-input');
    await input.fill('Como abrir um chamado de TI?');
    await input.press('Enter');

    // Exibe mensagem do usuário
    await expect(page.locator('.user-bubble .message-text')).toContainText('Como abrir um chamado de TI?');

    // Exibe resposta streamada
    const assistantBubble = page.locator('.assistant-bubble').last();
    await expect(assistantBubble.locator('.message-text')).toContainText('Para abrir um chamado de TI', { timeout: 10_000 });

    // Exibe painel de fontes
    await expect(assistantBubble.locator('.sources')).toBeVisible();
    await expect(assistantBubble.locator('.source-item')).toHaveCount(1);
    await expect(assistantBubble.locator('.src-name')).toContainText('Manual TI.pdf');
  });

  test('clica em sugestão e envia a pergunta', async ({ page }) => {
    await page.route('**/chat/stream', route => route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body: 'data: {"type":"token","text":"Resposta."}\n\ndata: {"type":"done"}\n\n',
    }));

    const chip = page.locator('.suggestion-chip').first();
    const chipText = await chip.textContent();
    await chip.click();

    const userMsg = page.locator('.user-bubble .message-text');
    await expect(userMsg).toContainText(chipText!.trim());
  });

  test('botão de envio desabilitado quando input vazio', async ({ page }) => {
    const sendBtn = page.locator('.send-btn');
    await expect(sendBtn).toBeDisabled();

    await page.locator('.question-input').fill('alguma pergunta');
    await expect(sendBtn).not.toBeDisabled();

    await page.locator('.question-input').fill('');
    await expect(sendBtn).toBeDisabled();
  });

  test('exibe indicador de carregamento durante streaming', async ({ page }) => {
    let resolveStream: () => void;
    const streamPromise = new Promise<void>(resolve => { resolveStream = resolve; });

    await page.route('**/chat/stream', async route => {
      await streamPromise;  // Mantém stream aberto até sinalizar
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
        body: 'data: {"type":"done"}\n\n',
      });
    });

    await page.locator('.question-input').fill('pergunta longa');
    await page.locator('.send-btn').click();

    // Indicador de streaming visível
    await expect(page.locator('.typing-indicator')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('.spinner')).toBeVisible();

    resolveStream!();
  });

  test('exibe erro quando API falha', async ({ page }) => {
    await page.route('**/chat/stream', route => route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body: 'data: {"type":"error","error":"Serviço indisponível"}\n\n',
    }));

    await page.locator('.question-input').fill('pergunta');
    await page.locator('.send-btn').click();

    await expect(page.locator('.assistant-bubble .message-text').last()).toContainText('Serviço indisponível', { timeout: 5000 });
  });

});

// ─── Source Panel ─────────────────────────────────────────────────────────────

test.describe('Source Panel', () => {

  test('exibe fonte de vídeo com timestamp clicável', async ({ page }) => {
    await page.route('**/chat/stream', route => route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body: [
        'data: {"type":"token","text":"No vídeo, explica em detalhes."}\n\n',
        'data: {"type":"sources","sources":[{"id":"v1","type":"video","name":"Onboarding RH.mp4","url":"https://blob/onb.mp4","timestamp_start":272,"timestamp_end":330,"sensitivity_label":"internal","relevance_score":0.95}]}\n\n',
        'data: {"type":"done"}\n\n',
      ].join(''),
    }));

    await page.locator('.question-input').fill('quando falam de férias no vídeo?');
    await page.locator('.send-btn').click();

    const sourceItem = page.locator('.source-item.video').first();
    await expect(sourceItem).toBeVisible({ timeout: 8000 });
    await expect(sourceItem).toContainText('04:32');
    await expect(sourceItem.locator('.src-icon')).toContainText('▶️');
  });

  test('exibe fonte de documento com número de página', async ({ page }) => {
    await page.route('**/chat/stream', route => route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body: [
        'data: {"type":"token","text":"Conforme o manual."}\n\n',
        'data: {"type":"sources","sources":[{"id":"d1","type":"document","name":"Política RH.pdf","url":"https://blob/rh.pdf","page":12,"sensitivity_label":"internal","relevance_score":0.88}]}\n\n',
        'data: {"type":"done"}\n\n',
      ].join(''),
    }));

    await page.locator('.question-input').fill('política de reembolso?');
    await page.locator('.send-btn').click();

    const sourceItem = page.locator('.source-item').first();
    await expect(sourceItem).toBeVisible({ timeout: 8000 });
    await expect(sourceItem).toContainText('Política RH.pdf');
    await expect(sourceItem.locator('.src-meta')).toContainText('Página 12');
  });

});

// ─── Navigation ───────────────────────────────────────────────────────────────

test.describe('Shell Navigation', () => {

  test('navega para todas as abas', async ({ page }) => {
    const tabs = [
      { label: 'Histórico',            path: '/history',   text: 'Histórico de Conversas' },
      { label: 'Base de Conhecimento', path: '/knowledge', text: 'Base de Conhecimento' },
      { label: 'Upload',               path: '/upload',    text: 'Adicionar Conhecimento' },
      { label: 'Dashboard',            path: '/dashboard', text: 'Dashboard' },
    ];

    for (const tab of tabs) {
      // Mock endpoints para cada aba
      await page.route('**' + tab.path.replace('/', '/api'), route => route.fulfill({
        status: 200, contentType: 'application/json', body: JSON.stringify([]),
      }));
      await page.route('**/conversations', route => route.fulfill({
        status: 200, contentType: 'application/json', body: JSON.stringify([]),
      }));
      await page.route('**/knowledge', route => route.fulfill({
        status: 200, contentType: 'application/json', body: JSON.stringify([]),
      }));
      await page.route('**/dashboard/metrics', route => route.fulfill({
        status: 403, contentType: 'application/json', body: '{}',
      }));

      const navLink = page.locator(`.nav-item >> text="${tab.label}"`);
      await navLink.click();
      await expect(page).toHaveURL(new RegExp(tab.path));
    }
  });

  test('sidebar exibe nome do usuário após autenticação', async ({ page }) => {
    await page.route('https://graph.microsoft.com/v1.0/me', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ displayName: 'Ana Silva', mail: 'ana@empresa.com', department: 'RH' }),
    }));

    await page.reload();
    await page.waitForLoadState('networkidle');

    await expect(page.locator('.user-name')).toContainText('Ana Silva', { timeout: 5000 });
    await expect(page.locator('.user-dept')).toContainText('RH');
  });

});

// ─── Upload ───────────────────────────────────────────────────────────────────

test.describe('Upload Component', () => {

  test('exibe zona de drop e aceita arquivos', async ({ page }) => {
    await page.goto(`${BASE_URL}/upload`);
    await page.waitForLoadState('networkidle');

    const dropZone = page.locator('.drop-zone');
    await expect(dropZone).toBeVisible();
    await expect(page.locator('.drop-content p')).toContainText('Arraste arquivos aqui');
  });

  test('exibe progresso de upload e status de processamento', async ({ page }) => {
    await page.goto(`${BASE_URL}/upload`);

    await page.route('**/ingest/upload', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ job_id: 'job-123', status: 'queued' }),
    }));

    await page.route('**/ingest/status/job-123', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ready', progress: 100 }),
    }));

    // Simula seleção de arquivo
    const input = page.locator('input[type="file"]');
    await input.setInputFiles({ name: 'manual.pdf', mimeType: 'application/pdf', buffer: Buffer.from('PDF content') });

    await expect(page.locator('.job-name')).toContainText('manual.pdf', { timeout: 3000 });
  });

});
