const ERROR_SELECTOR = [
  'app-error-message > .text-red-500',
  'app-validation-message > .text-red-500',
].join(',');

const FOCUSABLE_SELECTOR = [
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'button:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function isVisible(element: HTMLElement): boolean {
  return !!(
    element.offsetWidth ||
    element.offsetHeight ||
    element.getClientRects().length
  );
}

function findRelatedFocusable(errorElement: HTMLElement): HTMLElement | null {
  const localContainer = errorElement.closest('.flex.flex-col, .grid, app-section, form');
  return localContainer?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR) || null;
}

export function scrollToFirstFormError(form?: HTMLElement | null): void {
  if (!form) {
    return;
  }

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const firstError = Array.from(form.querySelectorAll<HTMLElement>(ERROR_SELECTOR))
        .find(element => isVisible(element) && !!element.textContent?.trim());

      if (!firstError) {
        return;
      }

      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      firstError.scrollIntoView({
        behavior: prefersReducedMotion ? 'auto' : 'smooth',
        block: 'center',
      });

      findRelatedFocusable(firstError)?.focus({ preventScroll: true });
    });
  });
}
