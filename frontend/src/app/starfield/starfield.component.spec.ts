import { ComponentFixture, TestBed } from '@angular/core/testing';
import { StarfieldComponent } from './starfield.component';
import { vi } from 'vitest';

describe('StarfieldComponent', () => {
  let component: StarfieldComponent;
  let fixture: ComponentFixture<StarfieldComponent>;

  beforeEach(async () => {
    // Mock canvas getContext so jsdom doesn't throw
    HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
      clearRect: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      stroke: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      fillRect: vi.fn(),
    }) as any;

    await TestBed.configureTestingModule({
      imports: [StarfieldComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(StarfieldComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    component.ngOnDestroy?.();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('renders a canvas element', () => {
    const canvas = fixture.nativeElement.querySelector('canvas');
    expect(canvas).toBeTruthy();
  });

  it('initialises stars on init', () => {
    expect(component.stars.length).toBeGreaterThan(0);
  });

  it('stops animation loop on destroy', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');
    component.ngOnDestroy();
    expect(cancelSpy).toHaveBeenCalled();
  });
});
