import { NgIf, CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../../services/authetication/auth.service';
import { NgForm, FormsModule } from '@angular/forms';

import { BaseInputComponent } from '../../../components/form/base-input/base-input.component';
import { CardComponent } from '../../../components/card/card.component';
@Component({
  selector: 'app-forgot-password',
  templateUrl: './reset-password.component.html',
  imports: [FormsModule, NgIf, CommonModule, BaseInputComponent, CardComponent]
})
export class ResetPasswordComponent implements OnInit {
  email = '';
  password = '';
  errorMessage: string | null = null;
  responseError = false;
  hasToken: boolean = false;
  token: string = '';
  confirmPassword: string = '';

  passwordStrength: 'weak' | 'medium' | 'strong' | null = null;
  showPasswordMeter = false;
  constructor(private router: Router, private route: ActivatedRoute, public auth_service: AuthService) {
  }
  onPasswordInput(password: string) {
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
  get isPasswordValid(): boolean {
    return this.password.length >= 8 && this.password === this.confirmPassword;
  }

  get pageTitle(): string {
    if (!this.hasToken) {
      return 'Forgot Password';
    }
    return 'Reset Password';
  }

  get pageSubtitle(): string {
    if (!this.hasToken) {
      return 'Enter your registered email to receive a password reset link.';
    }
    return 'Enter your new password';
  }

  get submitLabel(): string {
    if (!this.hasToken) {
      return 'Send Reset Link';
    }
    return 'Reset Password';
  }

  ngOnInit() {
    const token = this.route.snapshot.paramMap.get('token');
    if (token != null) {
      this.token = token;
      this.hasToken = true;

      this.auth_service.getInviteContext(token).subscribe({
        next: () => {
          this.router.navigate(['/invite', token], { replaceUrl: true }).then();
        },
        error: () => {
        }
      });
    }
  }
  onSubmit(form: NgForm) {
    this.errorMessage = '';
    if (form.valid) {
      if (this.hasToken) {
        if (this.password !== this.confirmPassword) {
          this.errorMessage = "Password and confirm password do not match";
          return;
        }

        this.auth_service.updatePassword(this.token, this.password).subscribe({
          next: (_) => {
            this.responseError = false;
            this.router.navigate(['login'], { replaceUrl: true }).then();
          },
          error: (err) => {
            this.responseError = true;
            if (err.status === 404) {
              this.errorMessage = "Invalid link";
            } else if (err.status === 400) {
              this.errorMessage = err?.error?.detail || "New password must be different from the old one.";
            } else {
              this.errorMessage = "Something went wrong. Please try again later.";
            }
          }
        });
      } else {
        this.auth_service.forgotPassword(this.email).subscribe({
          next: (_) => {
            this.responseError = false;
            this.router.navigate(['notification'], {
              state: {
                title: 'Password Reset Email Sent',
                description: 'A password reset link has been sent to your registered email address. Please check your inbox to continue.'
              }
            }).then();
          },
          error: (err) => {
            this.responseError = true;
            if (err.status === 404) {
              this.errorMessage = "Entered mail is not registered";
            } else {
              this.errorMessage = "Something went wrong. Please try again later.";
            }
          }
        });
      }
    }
  }
}
