# GuardGo - Quick Start Guide

Welcome to GuardGo! This guide will help you get the application up and running quickly.

## Prerequisites

- **Node.js:** v18.x or higher
- **npm:** v10.x or higher
- **Git:** Latest version

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/ibaslim/guardgo.git
cd guardgo
```

### 2. Install Dependencies

```bash
npm install
```

This will install all required Angular and development dependencies.

## Running the Application

### Development Server

Start the development server with hot-reload:

```bash
npm start
```

The application will be available at **http://localhost:4200**

### Production Build

Create an optimized production build:

```bash
npm run build
```

Build output will be in the `dist/guardgo-app` directory.

### Watch Mode (Development)

Run the build in watch mode for continuous compilation:

```bash
npm run watch
```

## Project Structure

```
guardgo/
├── src/                    # Source code
│   ├── app/               # Angular application
│   │   ├── pages/        # Page components
│   │   │   ├── onboarding/   # Signup page
│   │   │   ├── login/        # Login page
│   │   │   └── dashboard/    # Dashboard page
│   │   └── services/     # Services (Auth, etc.)
│   ├── index.html        # Main HTML file
│   ├── main.ts           # Application entry point
│   └── styles.css        # Global styles
├── backend/               # Backend (Python/Orion)
├── dist/                  # Build output (generated)
└── package.json           # Dependencies
```

## Available Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | Onboarding | Default route (redirects to onboarding) |
| `/onboarding` | Onboarding | User registration page |
| `/login` | Login | User authentication page |
| `/dashboard` | Dashboard | Main application dashboard |

## Features

### 🎨 User Interface
- Modern, responsive design with TailwindCSS
- Dark/Light mode support
- Collapsible sidebar navigation
- Beautiful gradients and shadows

### 🔐 Authentication
- User registration with validation
- Login functionality
- Session persistence
- Password strength requirements

### 📊 Dashboard
- Statistics cards (Users, Sessions, Response Time, Uptime)
- Recent activity feed
- User profile display
- Theme toggle

## Development Tips

### Testing the Application

1. **Test Registration:**
   - Navigate to http://localhost:4200/onboarding
   - Enter email and password (min 8 chars, 1 uppercase, 1 number)
   - Click "Create Account"

2. **Test Login:**
   - Navigate to http://localhost:4200/login
   - Enter any email and password
   - Click "Sign in"

3. **Test Dashboard:**
   - After login, you'll be redirected to the dashboard
   - Try collapsing the sidebar
   - Toggle dark mode
   - Click logout to return to login

### Hot Reload

The development server supports hot module replacement (HMR):
- Changes to TypeScript files auto-refresh
- CSS changes apply instantly
- Component changes reload the page

### Browser Console

Open browser DevTools (F12) to:
- View console logs
- Debug Angular components
- Inspect network requests
- Test responsive design

## Common Commands

```bash
# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build

# Run tests (when configured)
npm test

# Check for security vulnerabilities
npm audit

# Fix security vulnerabilities
npm audit fix
```

## Troubleshooting

### Port Already in Use

If port 4200 is already in use:

```bash
# Find the process using port 4200
lsof -i :4200

# Kill the process (replace PID with actual process ID)
kill -9 PID

# Or use a different port
ng serve --port 4201
```

### Build Errors

If you encounter build errors:

1. Delete node_modules and reinstall:
```bash
rm -rf node_modules
npm install
```

2. Clear Angular cache:
```bash
rm -rf .angular
```

3. Ensure you're using the correct Node.js version:
```bash
node --version  # Should be v18.x or higher
```

### Module Not Found

If you see "Module not found" errors:

```bash
npm install
```

## Configuration

### Environment Variables

Currently, the app uses in-browser storage. For backend integration, you'll need to add environment configuration:

```typescript
// src/environments/environment.ts
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api'
};
```

### Styling

The application uses TailwindCSS. Configuration is in `tailwind.config.js`:

```javascript
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  darkMode: 'class',
  // ... more config
}
```

## Next Steps

Now that you have the application running:

1. **Explore the Code:**
   - Check out `src/app/pages/` for page components
   - Review `src/app/services/auth.ts` for authentication logic
   - Look at `src/app/app.routes.ts` for routing

2. **Make Changes:**
   - Try modifying component templates
   - Add new routes
   - Customize the theme

3. **Add Features:**
   - Implement the "Forgot Password" flow
   - Create the Users page
   - Build the Analytics section
   - Add the Settings page

## Resources

- **Angular Documentation:** https://angular.dev
- **TailwindCSS Documentation:** https://tailwindcss.com
- **TypeScript Documentation:** https://www.typescriptlang.org

## Getting Help

If you encounter issues:

1. Check the browser console for errors
2. Review the Angular CLI output
3. Consult the Angular documentation
4. Check the project issues on GitHub

---

**Happy Coding! 🚀**
