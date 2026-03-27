import { NgIf, CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../../services/authetication/auth.service';
import { NgForm, FormsModule } from '@angular/forms';

import { BaseInputComponent } from '../../../components/form/base-input/base-input.component';
import { CardComponent } from '../../../components/card/card.component';

@Component({
  selector: 'app-invite-activation',
  templateUrl: './invite-activation.component.html',
  imports: [FormsModule, NgIf, CommonModule, BaseInputComponent, CardComponent]
})
export class InviteActivationComponent implements OnInit {
  token = '';
  username = '';
  fullName = '';
  password = '';
  confirmPassword = '';
  errorMessage: string | null = null;

  passwordStrength: 'weak' | 'medium' | 'strong' | null = null;
  showPasswordMeter = false;

  constructor(private router: Router, private route: ActivatedRoute, public auth_service: AuthService) {}

  get isPasswordValid(): boolean {
    return this.password.length >= 8 && this.password === this.confirmPassword;
  }

  ngOnInit(): void {
    const token = this.route.snapshot.paramMap.get('token');
    if (!token) {
      this.errorMessage = 'Invalid invite link';
      return;
    }

    this.token = token;
    this.auth_service.getInviteContext(token).subscribe({
      next: () => {},
      error: (err) => {
        if (err?.status === 404) {
          this.errorMessage = 'Invalid invite link';
        } else if (err?.status === 400) {
          this.errorMessage = err?.error?.detail || 'Invite link expired';
        } else {
          this.errorMessage = 'Something went wrong. Please try again later.';
        }
      }
    });
  }

  onPasswordInput(password: string): void {
    this.showPasswordMeter = password.length > 0;

    if (password.length < 8) {
      this.passwordStrength = 'weak';
      return;
    }

    if (password.length >= 12) {
      this.passwordStrength = 'strong';
    } else if (password.length >= 10) {
      this.passwordStrength = 'medium';
    } else {
      this.passwordStrength = 'weak';
    }
  }

  onSubmit(form: NgForm): void {
    this.errorMessage = '';

    if (!form.valid) {
      return;
    }

    if (this.password !== this.confirmPassword) {
      this.errorMessage = 'Password and confirm password do not match';
      return;
    }

    this.auth_service.activateInvite(this.token, this.password, this.username, this.fullName).subscribe({
      next: () => {
        this.router.navigate(['login'], { replaceUrl: true }).then();
      },
      error: (err) => {
        if (err.status === 404) {
          this.errorMessage = 'Invalid invite link';
        } else if (err.status === 400) {
          this.errorMessage = err?.error?.detail || 'Invite activation failed';
        } else {
          this.errorMessage = 'Something went wrong. Please try again later.';
        }
      }
    });
  }
}
