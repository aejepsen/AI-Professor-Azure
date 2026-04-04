import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ChatComponent } from './chat.component';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';
import { vi } from 'vitest';

async function* fakeStream(chunks: string[]) {
  for (const c of chunks) yield c;
}

describe('ChatComponent', () => {
  let component: ChatComponent;
  let fixture: ComponentFixture<ChatComponent>;
  let apiSpy: { chat: ReturnType<typeof vi.fn> };
  let authSpy: { getToken: ReturnType<typeof vi.fn>; isLoggedIn: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    apiSpy = { chat: vi.fn() };
    authSpy = {
      getToken: vi.fn().mockResolvedValue('fake-token'),
      isLoggedIn: vi.fn().mockReturnValue(true),
    };

    await TestBed.configureTestingModule({
      imports: [ChatComponent],
      providers: [
        { provide: ApiService, useValue: apiSpy },
        { provide: AuthService, useValue: authSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('adds user message to history after send', async () => {
    apiSpy.chat.mockReturnValue(fakeStream([]));
    component.query = 'Qual o tema da aula?';
    await component.send();

    expect(component.messages[0].role).toBe('user');
    expect(component.messages[0].text).toBe('Qual o tema da aula?');
  });

  it('accumulates SSE chunks into assistant message', async () => {
    apiSpy.chat.mockReturnValue(fakeStream(['Group', 'By ', 'é...']));
    component.query = 'O que é Group By?';
    await component.send();

    const assistant = component.messages.find(m => m.role === 'assistant');
    expect(assistant?.text).toBe('GroupBy é...');
  });

  it('clears query after send', async () => {
    apiSpy.chat.mockReturnValue(fakeStream([]));
    component.query = 'test';
    await component.send();

    expect(component.query).toBe('');
  });

  it('does not send empty query', async () => {
    component.query = '   ';
    await component.send();

    expect(apiSpy.chat).not.toHaveBeenCalled();
    expect(component.messages.length).toBe(0);
  });
});
