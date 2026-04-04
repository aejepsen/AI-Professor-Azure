import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavComponent } from './nav/nav.component';
import { StarfieldComponent } from './starfield/starfield.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, NavComponent, StarfieldComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {}
