import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ComponentsDemoComponent } from './components-demo.component';
import { ComponentsModule } from '../../components/components.module';

@NgModule({
  imports: [CommonModule, ComponentsModule, ComponentsDemoComponent],
  exports: [ComponentsDemoComponent]
})
export class ComponentsDemoModule {}
