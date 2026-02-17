import { Component } from '@angular/core';
import { AlertComponent } from '../../components/alert/alert.component';
import { ButtonComponent } from '../../components/button/button.component';
import { BadgeComponent } from '../../components/badge/badge.component';
import { AvatarComponent } from '../../components/avatar/avatar.component';
import { CardComponent } from '../../components/card/card.component';
import { TableComponent } from '../../components/table/table.component';
import { ModalComponent } from '../../components/modal/modal.component';
import { SideDrawerComponent } from '../../components/side-drawer/side-drawer.component';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-components-demo',
  standalone: true,
  imports: [
    CommonModule,
    AlertComponent,
    ButtonComponent,
    BadgeComponent,
    AvatarComponent,
    CardComponent,
    TableComponent,
    ModalComponent,
    SideDrawerComponent,
    FormsModule
  ],
  templateUrl: './components-demo.component.html'
})
export class ComponentsDemoComponent {
    showUserMenu = false;
    user = { name: 'Alice Smith', avatar: 'https://i.pravatar.cc/100?img=1' };

    // Close dropdown when clicking outside
    onClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('.user-menu-container')) {
        this.showUserMenu = false;
      }
    };

    ngOnInit() {
      document.addEventListener('mousedown', this.onClickOutside);
    }
    ngOnDestroy() {
      document.removeEventListener('mousedown', this.onClickOutside);
    }
  // Removed compact mode and columns feature
  showModal = false;
  showDrawer = false;
  drawerSize: 'sm' | 'md' | 'lg' | 'xl' | 'full' = 'lg';
  showClosableAlert = true;
  // Removed tableColumns
  tableData = [
    { FirstName: 'Alice', LastName: 'Smith', Email: 'alice@example.com', Role: 'Admin', Status: 'Active', Joined: '2024-01-10', Avatar: 'https://i.pravatar.cc/100?img=1' },
    { FirstName: 'Bob', LastName: 'Johnson', Email: 'bob@example.com', Role: 'User', Status: 'Inactive', Joined: '2023-12-22' },
    { FirstName: 'Charlie', LastName: 'Williams', Email: 'charlie@example.com', Role: 'Moderator', Status: 'Active', Joined: '2024-01-02', Avatar: 'https://i.pravatar.cc/100?img=3' },
    { FirstName: 'Diana', LastName: 'Brown', Email: 'diana@example.com', Role: 'User', Status: 'Active', Joined: '2024-01-12' },
    { FirstName: 'Eve', LastName: 'Davis', Email: 'eve@example.com', Role: 'Admin', Status: 'Inactive', Joined: '2023-11-30', Avatar: 'https://i.pravatar.cc/100?img=5' },
    { FirstName: 'Frank', LastName: 'Miller', Email: 'frank@example.com', Role: 'User', Status: 'Active', Joined: '2024-01-14' },
    { FirstName: 'Grace', LastName: 'Wilson', Email: 'grace@example.com', Role: 'Moderator', Status: 'Inactive', Joined: '2023-12-18', Avatar: 'https://i.pravatar.cc/100?img=7' },
    { FirstName: 'Heidi', LastName: 'Moore', Email: 'heidi@example.com', Role: 'User', Status: 'Active', Joined: '2024-01-09' },
    { FirstName: 'Ivan', LastName: 'Taylor', Email: 'ivan@example.com', Role: 'Admin', Status: 'Active', Joined: '2024-01-01', Avatar: 'https://i.pravatar.cc/100?img=9' },
    { FirstName: 'Judy', LastName: 'Anderson', Email: 'judy@example.com', Role: 'User', Status: 'Inactive', Joined: '2023-12-25' }
  ];
  loadingTable = false;
  emptyTable = false;
}
