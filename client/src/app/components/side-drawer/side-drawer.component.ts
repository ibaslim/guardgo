import { CommonModule } from '@angular/common';
import { Component, EventEmitter, HostListener, Input, Output } from '@angular/core';

@Component({
  selector: 'app-side-drawer',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './side-drawer.component.html'
})
export class SideDrawerComponent {
  private hideTimer: ReturnType<typeof setTimeout> | null = null;
  private animationFrameId: number | null = null;
  private _show = false;

  @Input()
  set show(value: boolean) {
    const next = !!value;
    this._show = next;

    if (next) {
      this.openDrawer();
      return;
    }

    this.closeDrawer();
  }

  get show(): boolean {
    return this._show;
  }

  @Input() size: 'sm' | 'md' | 'lg' | 'xl' | 'full' = 'lg';
  @Output() close = new EventEmitter<void>();
  rendered = false;
  visible = false;

  private openDrawer(): void {
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
    }
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    this.rendered = true;
    this.visible = false;
    this.animationFrameId = requestAnimationFrame(() => {
      this.animationFrameId = requestAnimationFrame(() => {
        this.visible = true;
        this.animationFrameId = null;
      });
    });
  }

  private closeDrawer(): void {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    this.visible = false;
    this.hideTimer = setTimeout(() => {
      this.rendered = false;
      this.hideTimer = null;
    }, 500);
  }

  @HostListener('document:keydown.escape', ['$event'])
  onEsc(_: Event): void {
    if (this.show) {
      this.close.emit();
    }
  }

  onBackdropClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('drawer-backdrop')) {
      this.close.emit();
    }
  }
}
