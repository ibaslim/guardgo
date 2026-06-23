const ERROR_SELECTOR = [
  'app-error-message > .text-red-500',
  'app-validation-message > .text-red-500',
].join(', ');

const FOCUSABLE_SELECTOR = [
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'button:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

export function scrollToFirstFormError(form: HTMLFormElement | null | undefined): void {
  if (!form) {
    return;
  }

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const errorElement = Array.from(form.querySelectorAll<HTMLElement>(ERROR_SELECTOR))
        .find((element) => element.textContent?.trim() && element.getClientRects().length > 0);

      if (!errorElement) {
        return;
      }

      const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      errorElement.scrollIntoView({
        behavior: reduceMotion ? 'auto' : 'smooth',
        block: 'center',
        inline: 'nearest',
      });

      const errorHost = errorElement.closest<HTMLElement>('app-error-message, app-validation-message');
      const localContainer = errorHost?.parentElement;
      const section = errorElement.closest<HTMLElement>('app-section');
      const focusTarget =
        localContainer?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
        || section?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);

      focusTarget?.focus({ preventScroll: true });
    });
  });
}
