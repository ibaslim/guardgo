import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { FormsModule, NgForm } from '@angular/forms';
import { AuthService } from '../../services/authetication/auth.service';
import { AppService } from '../../services/core/app/app.service';
import { RadioComponent } from "../../components/form/radio/radio.component";

@Component({
  selector: 'app-signup',
  standalone: true,
  imports: [FormsModule, CommonModule, BaseInputComponent, RadioComponent],
  templateUrl: './signup.component.html'
})
export class SignupComponent implements OnInit {
  user = { username: '', mail: '', password: '', confirmPassword: '', tenant_type: '' };
  errorMessage: string | null = null;
  showPasswordMeter = false;
  isMobile = false;

  usernamePattern = /^[A-Za-z][A-Za-z0-9_-]{7,19}$/;
  usernameSuggestion: string = '';

  constructor(private router: Router, public auth_service: AuthService, private route: ActivatedRoute, protected appService: AppService) { }

  ngOnInit(): void {
    this.route.queryParams.subscribe(() => {
      this.isMobile = window.innerWidth <= 480;
    });
  }

  validateUsername(): boolean {
    if (this.usernamePattern.test(this.user.username)) {
      this.usernameSuggestion = '';
      return true;
    }

    const suggestions: string[] = [];
    const base = this.user.username || '';
    let counter = 1;

    while (suggestions.length < 4 && counter < 50) {
      const suffix = counter.toString();
      let s = base.toLowerCase();

      if (!/^[A-Za-z]/.test(s)) {
        s = 'u' + s;
      }

      s = s.replace(/[^A-Za-z0-9_-]/g, '');

      if (s.length > 20 - suffix.length) {
        s = s.slice(0, 20 - suffix.length);
      }

      if (s.length < 8 - suffix.length) {
        s = s.padEnd(8 - suffix.length, '0');
      }

      const suggestion = s + suffix;

      if (this.usernamePattern.test(suggestion) && !suggestions.includes(suggestion)) {
        suggestions.push(suggestion);
      }

      counter++;
    }

    this.usernameSuggestion = suggestions.length
      ? 'Username already taken. Suggested usernames: ' + suggestions.join(', ')
      : 'Username already taken.';
    this.errorMessage = 'Invalid username';
    return false;
  }

  validateFields() {
    if (!this.validateUsername()) {
      return false;
    }

    const emailPattern = /^[\w.-]+@[\w.-]+\.\w+$/;

    if (!emailPattern.test(this.user.mail)) {
      this.errorMessage = 'Please enter a valid email address';
      return false;
    }

    if (this.user.password.length < 8) {
      this.errorMessage = 'Password must be at least 8 characters';
      return false;
    }

    if (this.user.password !== this.user.confirmPassword) {
      this.errorMessage = 'Passwords do not match';
      return false;
    }

    if (!this.user.tenant_type) {
      this.errorMessage = 'Please select a domain';
      return false;
    }

    this.errorMessage = null;
    return true;
  }

  onPasswordInput(password: string) {
    this.showPasswordMeter = password.length > 0;
  }

  get isPasswordValid(): boolean {
    return this.user.password.length >= 8 && this.user.password === this.user.confirmPassword;
  }

  roles = [
    { label: 'Client', value: 'client' },
    { label: 'Guard', value: 'guard' },
    { label: 'Service Provider', value: 'service_provider' }
  ];

  onSubmit(form: NgForm) {
    if (!this.validateFields() || !form.valid) return;

    this.auth_service.signup(this.user.username, this.user.mail, this.user.password, this.user.tenant_type).subscribe({
      next: () => this.router.navigate(['/welcome']),
      error: (err) => {
        this.errorMessage = err?.error?.detail || 'Signup failed';
      }
    });
  }

  goToLogin() {
    this.router.navigate(['/login']).then();
  }
}
