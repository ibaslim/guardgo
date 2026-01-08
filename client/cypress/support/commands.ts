export {};

declare global {
  namespace Cypress {
    interface Chainable {
      loginAsAdmin(): Chainable<void>;
    }
  }
}

export {};

declare global {
  namespace Cypress {
    interface Chainable {
      loginAsAdmin(): Chainable<void>;
    }
  }
}

Cypress.Commands.add("loginAsAdmin", () => {
});
