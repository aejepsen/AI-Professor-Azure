import { TestBed } from '@angular/core/testing';
import { AuthService } from './auth.service';
import { vi } from 'vitest';

const mockMsal = {
  instance: {
    getAllAccounts: vi.fn().mockReturnValue([]),
    acquireTokenSilent: vi.fn(),
    loginRedirect: vi.fn(),
    logoutRedirect: vi.fn(),
  },
};

describe('AuthService', () => {
  let service: AuthService;

  beforeEach(() => {
    vi.clearAllMocks();
    mockMsal.instance.getAllAccounts.mockReturnValue([]);

    TestBed.configureTestingModule({
      providers: [
        AuthService,
        { provide: 'MSAL_INSTANCE', useValue: mockMsal.instance },
      ],
    });
    service = TestBed.inject(AuthService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('isLoggedIn() returns false when no accounts', () => {
    mockMsal.instance.getAllAccounts.mockReturnValue([]);
    expect(service.isLoggedIn()).toBe(false);
  });

  it('isLoggedIn() returns true when account exists', () => {
    mockMsal.instance.getAllAccounts.mockReturnValue([{ username: 'user@test.com' }]);
    expect(service.isLoggedIn()).toBe(true);
  });

  it('login() calls loginRedirect', () => {
    service.login();
    expect(mockMsal.instance.loginRedirect).toHaveBeenCalled();
  });

  it('logout() calls logoutRedirect', () => {
    service.logout();
    expect(mockMsal.instance.logoutRedirect).toHaveBeenCalled();
  });

  it('getToken() returns null when not logged in', async () => {
    mockMsal.instance.getAllAccounts.mockReturnValue([]);
    const token = await service.getToken();
    expect(token).toBeNull();
  });

  it('getToken() acquires token silently when logged in', async () => {
    const fakeAccount = { username: 'user@test.com' };
    mockMsal.instance.getAllAccounts.mockReturnValue([fakeAccount]);
    mockMsal.instance.acquireTokenSilent.mockResolvedValue({ accessToken: 'my-token' });

    const token = await service.getToken();
    expect(token).toBe('my-token');
    expect(mockMsal.instance.acquireTokenSilent).toHaveBeenCalledWith(
      expect.objectContaining({ account: fakeAccount })
    );
  });
});
