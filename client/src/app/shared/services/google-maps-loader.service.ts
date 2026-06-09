import { Injectable } from '@angular/core';

import { AppService } from '../../services/core/app/app.service';

declare global {
  interface Window {
    google?: any;
    __guardGoGoogleMapsInit?: () => void;
  }
}

export interface LoadedGoogleMapsApi {
  google: any;
  mapsLibrary: any;
  placesLibrary: any;
}

@Injectable({
  providedIn: 'root',
})
export class GoogleMapsLoaderService {
  private loadPromise: Promise<LoadedGoogleMapsApi> | null = null;

  constructor(private readonly appService: AppService) {}

  async load(): Promise<LoadedGoogleMapsApi> {
    const settings = await this.waitForRuntimeConfig();
    const apiKey = String(settings.google_maps_api_key || '').trim();
    const enabled = String(settings.google_maps_enabled || '0') === '1' && !!apiKey;

    if (!enabled) {
      throw new Error('Google Maps is not configured for this environment.');
    }

    if (!this.loadPromise) {
      this.loadPromise = this.ensureScript(apiKey)
        .then(async () => {
          if (!window.google?.maps?.importLibrary) {
            throw new Error('Google Maps failed to initialize.');
          }

          const mapsLibrary = await window.google.maps.importLibrary('maps');
          const placesLibrary = await window.google.maps.importLibrary('places');
          return {
            google: window.google,
            mapsLibrary,
            placesLibrary,
          };
        })
        .catch((error) => {
          this.loadPromise = null;
          throw error;
        });
    }

    return this.loadPromise;
  }

  getRuntimeOptions(): { mapId?: string; countryRestriction?: string } {
    const settings = this.appService.getConfig().appSettings;
    const mapId = String(settings.google_maps_map_id || '').trim();
    const countryRestriction = String(settings.google_maps_country_restriction || '').trim().toLowerCase();
    return {
      mapId: mapId || undefined,
      countryRestriction: countryRestriction || undefined,
    };
  }

  private ensureScript(apiKey: string): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const resolveWhenReady = () => {
        void this.waitForGoogleMapsGlobal()
          .then(() => resolve())
          .catch(reject);
      };

      const existingScript = document.getElementById('google-maps-js-api') as HTMLScriptElement | null;
      if (existingScript) {
        if (window.google?.maps?.importLibrary) {
          resolve();
          return;
        }
        existingScript.addEventListener('load', () => resolveWhenReady(), { once: true });
        existingScript.addEventListener('error', () => reject(new Error('Failed to load Google Maps.')), { once: true });
        resolveWhenReady();
        return;
      }

      window.__guardGoGoogleMapsInit = () => {
        resolveWhenReady();
      };

      const script = document.createElement('script');
      script.id = 'google-maps-js-api';
      script.async = true;
      script.defer = true;
      script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=places&loading=async&v=beta&callback=__guardGoGoogleMapsInit`;
      script.onload = () => resolveWhenReady();
      script.onerror = () => reject(new Error('Failed to load Google Maps.'));
      document.head.appendChild(script);
    });
  }

  private async waitForGoogleMapsGlobal(maxAttempts = 50, delayMs = 100): Promise<void> {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      if (window.google?.maps?.importLibrary) {
        return;
      }

      await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    }

    throw new Error('Google Maps failed to initialize.');
  }

  private async waitForRuntimeConfig(maxAttempts = 4, delayMs = 350): Promise<ReturnType<AppService['getConfig']>['appSettings']> {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const currentSettings = this.appService.getConfig().appSettings;
      const currentApiKey = String(currentSettings.google_maps_api_key || '').trim();
      const currentEnabled = String(currentSettings.google_maps_enabled || '0') === '1';
      if (currentEnabled && currentApiKey) {
        return currentSettings;
      }

      await this.appService.loadConfig(attempt > 0);

      const refreshedSettings = this.appService.getConfig().appSettings;
      const refreshedApiKey = String(refreshedSettings.google_maps_api_key || '').trim();
      const refreshedEnabled = String(refreshedSettings.google_maps_enabled || '0') === '1';
      if (refreshedEnabled && refreshedApiKey) {
        return refreshedSettings;
      }

      if (attempt < maxAttempts - 1) {
        await new Promise((resolve) => window.setTimeout(resolve, delayMs));
      }
    }

    return this.appService.getConfig().appSettings;
  }
}
