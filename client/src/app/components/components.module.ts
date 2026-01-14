import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonComponent } from './button/button.component';
import { ModalComponent } from './modal/modal.component';
import { CardComponent } from './card/card.component';
import { TableComponent } from './table/table.component';
import { AlertComponent } from './alert/alert.component';
import { LoaderComponent } from './loader/loader.component';
import { BadgeComponent } from './badge/badge.component';
import { AvatarComponent } from './avatar/avatar.component';

@NgModule({
  imports: [
    CommonModule,
    ButtonComponent,
    ModalComponent,
    CardComponent,
    TableComponent,
    AlertComponent,
    LoaderComponent,
    BadgeComponent,
    AvatarComponent
  ],
  declarations: [
  ],
  exports: [
    ButtonComponent,
    ModalComponent,
    CardComponent,
    TableComponent,
    AlertComponent,
    LoaderComponent,
    BadgeComponent,
    AvatarComponent
  ]
})
export class ComponentsModule {}
