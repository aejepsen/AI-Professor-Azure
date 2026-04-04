import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NavComponent } from './nav.component';
import { AuthService } from '../services/auth.service';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

describe('NavComponent', () => {
  let component: NavComponent;
  let fixture: ComponentFixture<NavComponent>;
  let loggedIn = false;
  let authSpy: { isLoggedIn: ReturnType<typeof vi.fn>; login: ReturnType<typeof vi.fn>; logout: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    loggedIn = false;
    authSpy = {
      isLoggedIn: vi.fn().mockImplementation(() => loggedIn),
      login: vi.fn(),
      logout: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [NavComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(NavComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
  });

  it('shows login button when not logged in', () => {
    loggedIn = false;
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="btn-login"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="btn-logout"]')).toBeFalsy();
  });

  it('shows logout button when logged in', () => {
    loggedIn = true;
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="btn-logout"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="btn-login"]')).toBeFalsy();
  });

  it('calls login() when login button is clicked', () => {
    loggedIn = false;
    fixture.detectChanges();
    const btn = fixture.nativeElement.querySelector('[data-testid="btn-login"]') as HTMLButtonElement;
    btn.click();
    expect(authSpy.login).toHaveBeenCalled();
  });

  it('calls logout() when logout button is clicked', () => {
    loggedIn = true;
    fixture.detectChanges();
    const btn = fixture.nativeElement.querySelector('[data-testid="btn-logout"]') as HTMLButtonElement;
    btn.click();
    expect(authSpy.logout).toHaveBeenCalled();
  });
});
