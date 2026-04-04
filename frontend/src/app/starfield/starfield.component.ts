import { Component, ElementRef, OnDestroy, AfterViewInit, ViewChild } from '@angular/core';

interface Star {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
}

const STAR_COUNT = 120;
const CONNECT_DIST = 120;
const SPEED = 0.3;

@Component({
  selector: 'app-starfield',
  standalone: true,
  imports: [],
  templateUrl: './starfield.component.html',
  styleUrl: './starfield.component.scss',
})
export class StarfieldComponent implements AfterViewInit, OnDestroy {
  @ViewChild('canvas', { static: true }) canvasRef!: ElementRef<HTMLCanvasElement>;

  stars: Star[] = [];
  private animId = 0;
  private ctx!: CanvasRenderingContext2D;

  ngAfterViewInit(): void {
    const canvas = this.canvasRef.nativeElement;
    this.ctx = canvas.getContext('2d')!;
    this.resize(canvas);
    window.addEventListener('resize', () => this.resize(canvas));
    this.initStars(canvas.width, canvas.height);
    this.loop();
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.animId);
  }

  private resize(canvas: HTMLCanvasElement): void {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  private initStars(w: number, h: number): void {
    this.stars = Array.from({ length: STAR_COUNT }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * SPEED,
      vy: (Math.random() - 0.5) * SPEED,
      radius: Math.random() * 1.5 + 0.5,
    }));
  }

  private loop(): void {
    this.animId = requestAnimationFrame(() => this.loop());
    this.draw();
  }

  private draw(): void {
    const { ctx } = this;
    const { width: w, height: h } = this.canvasRef.nativeElement;

    ctx.clearRect(0, 0, w, h);

    for (const s of this.stars) {
      s.x += s.vx;
      s.y += s.vy;
      if (s.x < 0) s.x = w;
      if (s.x > w) s.x = 0;
      if (s.y < 0) s.y = h;
      if (s.y > h) s.y = 0;

      ctx.beginPath();
      ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(100,220,200,0.85)';
      ctx.fill();
    }

    for (let i = 0; i < this.stars.length; i++) {
      for (let j = i + 1; j < this.stars.length; j++) {
        const dx = this.stars[i].x - this.stars[j].x;
        const dy = this.stars[i].y - this.stars[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < CONNECT_DIST) {
          ctx.beginPath();
          ctx.moveTo(this.stars[i].x, this.stars[i].y);
          ctx.lineTo(this.stars[j].x, this.stars[j].y);
          ctx.strokeStyle = `rgba(100,220,200,${(1 - dist / CONNECT_DIST) * 0.3})`;
          ctx.stroke();
        }
      }
    }
  }
}
