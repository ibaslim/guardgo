# GuardGo

> A modern, full-stack dashboard application with authentication and analytics

[![Angular](https://img.shields.io/badge/Angular-21.0.0-red)](https://angular.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9.2-blue)](https://www.typescriptlang.org)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4.17-38B2AC)](https://tailwindcss.com)

## 📋 Overview

GuardGo is a professional-grade Angular application featuring a complete authentication system, responsive dashboard, and modern UI/UX design. Built with Angular 21 and styled with TailwindCSS, it provides a solid foundation for building secure, scalable web applications.

## ✨ Features

- 🔐 **Complete Authentication Flow** - Registration and login with validation
- 📊 **Interactive Dashboard** - Real-time statistics and activity feed
- 🌓 **Dark Mode Support** - Toggle between light and dark themes
- 📱 **Responsive Design** - Works seamlessly on all devices
- 🎨 **Modern UI/UX** - Clean design with TailwindCSS
- ⚡ **Fast Performance** - Optimized build with Angular CLI and Vite

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm start

# Open http://localhost:4200
```

See [QUICK_START.md](QUICK_START.md) for detailed setup instructions.

## 📸 Screenshots

### Onboarding Page
Clean registration interface with password validation.

### Login Page
Simple and secure authentication.

### Dashboard (Light Mode)
Feature-rich dashboard with statistics and activity feed.

### Dashboard (Dark Mode)
Full dark mode support for comfortable viewing.

## 🏗️ Project Structure

```
guardgo/
├── src/app/
│   ├── pages/           # Page components
│   ├── services/        # Business logic services
│   └── app.routes.ts    # Application routing
├── backend/             # Backend services (Orion framework)
├── docs/                # Documentation
└── package.json         # Dependencies
```

## 🛠️ Technology Stack

### Frontend
- **Angular 21** - Modern web framework
- **TypeScript 5.9** - Type-safe JavaScript
- **TailwindCSS 3.4** - Utility-first CSS
- **RxJS 7.8** - Reactive programming
- **Vitest 4.0** - Fast unit testing

### Backend
- **Orion Framework** - Python-based backend
- API structure ready for integration

## 📖 Documentation

- [Project Analysis](PROJECT_ANALYSIS.md) - Comprehensive project analysis
- [Quick Start Guide](QUICK_START.md) - Getting started guide
- [Angular Documentation](https://angular.dev) - Official Angular docs

## 🔧 Development

### Available Scripts

```bash
npm start        # Start development server
npm run build    # Build for production
npm run watch    # Build in watch mode
npm test         # Run tests
```

### Code Structure

- **Components** - Located in `src/app/pages/`
- **Services** - Located in `src/app/services/`
- **Routing** - Configured in `src/app/app.routes.ts`
- **Styles** - TailwindCSS utilities in component files

## 🎯 Current Features

### Authentication
- ✅ User registration with validation
- ✅ Login functionality
- ✅ Session persistence
- ✅ Logout capability
- 🔄 Password reset (UI ready)

### Dashboard
- ✅ Statistics cards (Users, Sessions, Response Time, Uptime)
- ✅ Recent activity timeline
- ✅ Collapsible sidebar navigation
- ✅ Dark/Light mode toggle
- ✅ User profile display

## 🚧 Roadmap

- [ ] Backend API integration
- [ ] Real-time data updates
- [ ] Users management page
- [ ] Analytics visualization page
- [ ] Settings and configuration page
- [ ] Advanced authentication (2FA, OAuth)
- [ ] Notification system
- [ ] Export/Import functionality

## 🤝 Contributing

This is a private project. For authorized contributors:

1. Create a feature branch
2. Make your changes
3. Submit a pull request
4. Wait for review

## 📝 License

Private project - All rights reserved

## 👤 Author

**GuardGo Development Team**

## 🙏 Acknowledgments

Built with modern web technologies:
- Angular team for the amazing framework
- TailwindCSS for the utility-first CSS
- The open-source community

---

**Ready to build amazing things with GuardGo! 🚀**
