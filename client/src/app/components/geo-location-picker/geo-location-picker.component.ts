import { CommonModule } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { BannerComponent } from '../banner/banner.component';
import { ButtonComponent } from '../button/button.component';
import { BaseInputComponent } from '../form/base-input/base-input.component';
import { ValidationMessageComponent } from '../validation-message/validation-message.component';
import {
  formatCoordinateInput,
  isLatitudeInRange,
  isLongitudeInRange,
  parseCoordinate,
} from '../../shared/helpers/location.helper';
import {
  GeoLocationSelection,
  buildGoogleMapsLocationUrl,
  mapGoogleAddressResultToSelection,
} from '../../shared/helpers/google-maps-address.helper';
import { GoogleMapsLoaderService, LoadedGoogleMapsApi } from '../../shared/services/google-maps-loader.service';

interface GoogleMapsPrediction {
  description: string;
  secondaryText: string;
  placePrediction: any | null;
  legacyPrediction?: any | null;
  placeId?: string;
}

@Component({
  selector: 'app-geo-location-picker',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    BannerComponent,
    BaseInputComponent,
    ButtonComponent,
    ValidationMessageComponent,
  ],
  templateUrl: './geo-location-picker.component.html',
})
export class GeoLocationPickerComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('mapCanvas') private readonly mapCanvas?: ElementRef<HTMLDivElement>;

  @Input() title = 'Geo Location';
  @Input() helperText = 'Capture coordinates to improve matching accuracy and shift geofencing.';
  @Input() disabled = false;
  @Input() readonly = false;
  @Input() showMapUrl = true;
  @Input() showSearchInput = true;
  @Input() showCoordinateInputs = true;
  @Input() showActionButtons = true;
  @Input() mapUrl = '';
  @Output() mapUrlChange = new EventEmitter<string>();
  @Input() mapUrlLabel = 'Map Link';
  @Input() mapUrlName = 'mapUrl';
  @Input() mapUrlPlaceholder = 'Paste a Google Maps or OpenStreetMap link';
  @Input() searchQuery = '';
  @Input() searchSummary = '';
  @Input() latitude = '';
  @Output() latitudeChange = new EventEmitter<string>();
  @Input() longitude = '';
  @Output() longitudeChange = new EventEmitter<string>();
  @Output() locationChange = new EventEmitter<GeoLocationSelection>();
  @Input() latitudeLabel = 'Latitude';
  @Input() longitudeLabel = 'Longitude';
  @Input() latitudeName = 'latitude';
  @Input() longitudeName = 'longitude';
  @Input() latitudePlaceholder = '43.6532';
  @Input() longitudePlaceholder = '-79.3832';
  @Input() latitudeError = '';
  @Input() longitudeError = '';
  @Input() coordinateError = '';
  @Input() previewHeightPx = 220;

  googleMapsReady = false;
  loadingMaps = false;
  capturingLocation = false;
  pickerMessage = '';
  pickerError = '';
  predictions: GoogleMapsPrediction[] = [];
  searchingPredictions = false;

  private googleApi: any;
  private mapsLibrary: any;
  private placesLibrary: any;
  private map: any;
  private marker: any;
  private geocoder: any;
  private legacyAutocompleteService: any;
  private legacyPlacesService: any;
  private autocompleteSessionToken: any | null = null;
  private searchDebounceId: number | null = null;

  constructor(private readonly mapsLoader: GoogleMapsLoaderService) {}

  async ngAfterViewInit(): Promise<void> {
    window.setTimeout(() => {
      if (!String(this.searchQuery || '').trim()) {
        this.searchQuery = String(this.searchSummary || '').trim();
      }
      void this.initializeGoogleMaps();
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['searchSummary'] && !this.searchQuery.trim()) {
      this.searchQuery = String(this.searchSummary || '').trim();
    }

    if ((changes['latitude'] || changes['longitude']) && this.googleMapsReady) {
      this.syncMapToInputCoordinates();
    }
  }

  ngOnDestroy(): void {
    if (this.searchDebounceId !== null) {
      window.clearTimeout(this.searchDebounceId);
    }
  }

  onSearchQueryInput(value: string): void {
    this.searchQuery = value;
    this.pickerError = '';
    this.pickerMessage = '';

    if (!this.googleMapsReady || this.disabled || this.readonly) {
      return;
    }

    if (this.searchDebounceId !== null) {
      window.clearTimeout(this.searchDebounceId);
    }

    const trimmed = String(value || '').trim();
    if (trimmed.length < 2) {
      this.predictions = [];
      this.searchingPredictions = false;
      return;
    }

    this.searchDebounceId = window.setTimeout(() => {
      this.fetchPredictions(trimmed);
    }, 250);
  }

  onLatitudeInput(value: string): void {
    this.latitude = value;
    this.latitudeChange.emit(value);
    this.syncMapToInputCoordinates();
  }

  onLongitudeInput(value: string): void {
    this.longitude = value;
    this.longitudeChange.emit(value);
    this.syncMapToInputCoordinates();
  }

  async selectPrediction(prediction: GoogleMapsPrediction): Promise<void> {
    if (!this.googleMapsReady) {
      return;
    }

    this.predictions = [];
    this.searchingPredictions = true;
    this.pickerError = '';
    try {
      if (prediction.placePrediction) {
        const place = prediction.placePrediction.toPlace();
        await place.fetchFields({
          fields: ['displayName', 'formattedAddress', 'location', 'addressComponents', 'googleMapsURI'],
        });

        const latitude = Number(place?.location?.lat?.());
        const longitude = Number(place?.location?.lng?.());
        if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
          this.pickerError = 'Unable to load the selected Google Maps location.';
          return;
        }

        const selection = mapGoogleAddressResultToSelection(place, latitude, longitude);
        this.applySelection(selection, true);
        this.autocompleteSessionToken = null;
        return;
      }

      if (prediction.placeId) {
        const selection = await this.loadLegacyPlaceSelection(prediction.placeId);
        if (selection) {
          this.applySelection(selection, true);
          this.autocompleteSessionToken = null;
          return;
        }
      }

      this.pickerError = 'Unable to load the selected Google Maps location.';
    } catch {
      if (prediction.placeId) {
        const selection = await this.loadLegacyPlaceSelection(prediction.placeId);
        if (selection) {
          this.applySelection(selection, true);
          this.autocompleteSessionToken = null;
          this.searchingPredictions = false;
          return;
        }
      }
      this.pickerError = 'Unable to load the selected Google Maps location.';
    } finally {
      this.searchingPredictions = false;
    }
  }

  captureCurrentLocation(): void {
    if (this.disabled || this.readonly || this.capturingLocation || !this.canUseBrowserGeolocation) {
      return;
    }

    this.capturingLocation = true;
    this.pickerError = '';
    this.pickerMessage = '';
    navigator.geolocation.getCurrentPosition(
      (position) => {
        this.capturingLocation = false;
        this.applyCoordinates(position.coords.latitude, position.coords.longitude, { reverseGeocode: true, successMessage: 'Current device location captured.' });
      },
      (error) => {
        this.capturingLocation = false;
        switch (error.code) {
          case error.PERMISSION_DENIED:
            this.pickerError = 'Location access was denied by the browser.';
            break;
          case error.POSITION_UNAVAILABLE:
            this.pickerError = 'Current location is unavailable on this device.';
            break;
          case error.TIMEOUT:
            this.pickerError = 'Location capture timed out. Try again.';
            break;
          default:
            this.pickerError = 'Unable to capture the current location.';
            break;
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  }

  clearCoordinates(): void {
    this.onLatitudeInput('');
    this.onLongitudeInput('');
    this.mapUrl = '';
    this.mapUrlChange.emit(this.mapUrl);
    this.searchQuery = String(this.searchSummary || '').trim();
    this.predictions = [];
    this.autocompleteSessionToken = null;
    this.pickerMessage = '';
    this.pickerError = '';
    if (this.marker) {
      this.marker.setMap(null);
      this.marker = null;
    }
  }

  get canUseBrowserGeolocation(): boolean {
    return typeof navigator !== 'undefined' && !!navigator.geolocation;
  }

  get openInGoogleMapsUrl(): string {
    if (String(this.mapUrl || '').trim()) {
      return this.mapUrl;
    }

    const coordinates = this.coordinatePair;
    if (!coordinates) {
      return '';
    }

    return buildGoogleMapsLocationUrl(coordinates[0], coordinates[1]);
  }

  private async initializeGoogleMaps(): Promise<void> {
    if (!this.mapCanvas?.nativeElement) {
      return;
    }

    this.loadingMaps = true;
    this.pickerError = '';
    try {
      const loadedGoogleMaps = await this.mapsLoader.load();
      this.bindLoadedLibraries(loadedGoogleMaps);
      this.googleMapsReady = true;
      const runtimeOptions = this.mapsLoader.getRuntimeOptions();
      const initialCoordinates = this.coordinatePair || [56.1304, -106.3468];
      const mapOptions: any = {
        center: { lat: initialCoordinates[0], lng: initialCoordinates[1] },
        zoom: this.coordinatePair ? 14 : 4,
        streetViewControl: false,
        mapTypeControl: false,
        fullscreenControl: false,
      };
      if (runtimeOptions.mapId) {
        mapOptions.mapId = runtimeOptions.mapId;
      }

      this.map = new this.mapsLibrary.Map(this.mapCanvas.nativeElement, mapOptions);
      this.geocoder = new this.googleApi.maps.Geocoder();
      if (this.googleApi?.maps?.places?.AutocompleteService) {
        this.legacyAutocompleteService = new this.googleApi.maps.places.AutocompleteService();
      }
      if (this.googleApi?.maps?.places?.PlacesService) {
        this.legacyPlacesService = new this.googleApi.maps.places.PlacesService(this.map);
      }

      this.map.addListener('click', (event: any) => {
        if (this.disabled || this.readonly || !event?.latLng) {
          return;
        }
        this.applyCoordinates(Number(event.latLng.lat()), Number(event.latLng.lng()), {
          reverseGeocode: true,
          successMessage: 'Location updated from the map.',
        });
      });

      this.syncMapToInputCoordinates();
    } catch (error: any) {
      this.googleMapsReady = false;
      this.pickerError = error?.message || 'Google Maps could not be loaded.';
    } finally {
      this.loadingMaps = false;
    }
  }

  private get coordinatePair(): [number, number] | null {
    const latitude = parseCoordinate(this.latitude);
    const longitude = parseCoordinate(this.longitude);
    if (!isLatitudeInRange(latitude) || !isLongitudeInRange(longitude)) {
      return null;
    }
    return [latitude, longitude];
  }

  private fetchPredictions(query: string): void {
    this.searchingPredictions = true;
    const runtimeOptions = this.mapsLoader.getRuntimeOptions();
    if (!this.placesLibrary?.AutocompleteSuggestion) {
      void this.fetchLegacyPredictions(query, runtimeOptions.countryRestriction);
      return;
    }

    if (!this.autocompleteSessionToken && this.placesLibrary?.AutocompleteSessionToken) {
      this.autocompleteSessionToken = new this.placesLibrary.AutocompleteSessionToken();
    }

    const request: any = {
      input: query,
      inputOffset: query.length,
    };
    if (this.autocompleteSessionToken) {
      request.sessionToken = this.autocompleteSessionToken;
    }
    if (runtimeOptions.countryRestriction) {
      request.includedRegionCodes = [runtimeOptions.countryRestriction];
      request.region = runtimeOptions.countryRestriction;
    }

    void this.placesLibrary.AutocompleteSuggestion.fetchAutocompleteSuggestions(request)
      .then((result: any) => {
        const suggestions = Array.isArray(result?.suggestions) ? result.suggestions : [];
        this.predictions = suggestions
          .map((suggestion: any) => {
            const placePrediction = suggestion?.placePrediction;
            if (!placePrediction) {
              return null;
            }
            return {
              description: String(placePrediction?.text?.text || '').trim(),
              secondaryText: String(placePrediction?.secondaryText?.text || '').trim(),
              placePrediction,
              placeId: String(placePrediction?.placeId || placePrediction?.place || '').trim(),
            };
          })
          .filter((prediction: GoogleMapsPrediction | null): prediction is GoogleMapsPrediction => !!prediction);
        this.pickerError = '';
      })
      .catch(() => {
        void this.fetchLegacyPredictions(query, runtimeOptions.countryRestriction);
      })
      .finally(() => {
        this.searchingPredictions = false;
      });
  }

  private bindLoadedLibraries(loadedGoogleMaps: LoadedGoogleMapsApi): void {
    this.googleApi = loadedGoogleMaps.google;
    this.mapsLibrary = loadedGoogleMaps.mapsLibrary;
    this.placesLibrary = loadedGoogleMaps.placesLibrary;
  }

  private async fetchLegacyPredictions(query: string, countryRestriction?: string): Promise<void> {
    if (!this.legacyAutocompleteService) {
      this.predictions = [];
      this.searchingPredictions = false;
      this.pickerError = 'Google Maps search is unavailable for this environment.';
      return;
    }

    const request: any = {
      input: query,
    };
    if (countryRestriction) {
      request.componentRestrictions = { country: countryRestriction };
    }

    await new Promise<void>((resolve) => {
      this.legacyAutocompleteService.getPlacePredictions(request, (predictions: any[], status: string) => {
        const okStatus = this.googleApi?.maps?.places?.PlacesServiceStatus?.OK || 'OK';
        if (status !== okStatus || !Array.isArray(predictions)) {
          this.predictions = [];
          this.pickerError = 'Google Maps search failed. Check the browser API key restrictions.';
          resolve();
          return;
        }

        this.predictions = predictions.map((prediction: any) => ({
          description: String(prediction?.description || '').trim(),
          secondaryText: String(prediction?.structured_formatting?.secondary_text || '').trim(),
          placePrediction: null,
          legacyPrediction: prediction,
          placeId: String(prediction?.place_id || '').trim(),
        }));
        this.pickerError = '';
        resolve();
      });
    });

    this.searchingPredictions = false;
  }

  private async loadLegacyPlaceSelection(placeId: string): Promise<GeoLocationSelection | null> {
    if (!this.legacyPlacesService || !String(placeId || '').trim()) {
      return null;
    }

    return new Promise<GeoLocationSelection | null>((resolve) => {
      this.legacyPlacesService.getDetails(
        {
          placeId,
          fields: ['formatted_address', 'geometry', 'address_components', 'place_id', 'url', 'name'],
        },
        (place: any, status: string) => {
          const okStatus = this.googleApi?.maps?.places?.PlacesServiceStatus?.OK || 'OK';
          const latitude = Number(place?.geometry?.location?.lat?.());
          const longitude = Number(place?.geometry?.location?.lng?.());
          if (status !== okStatus || !place || !Number.isFinite(latitude) || !Number.isFinite(longitude)) {
            resolve(null);
            return;
          }

          resolve(mapGoogleAddressResultToSelection(place, latitude, longitude, placeId));
        },
      );
    });
  }

  private syncMapToInputCoordinates(): void {
    const coordinates = this.coordinatePair;
    if (!this.googleMapsReady || !this.map || !coordinates) {
      return;
    }

    this.setMarker(coordinates[0], coordinates[1], false);
    this.map.panTo({ lat: coordinates[0], lng: coordinates[1] });
    if (!this.map.getZoom || this.map.getZoom() < 12) {
      this.map.setZoom(14);
    }
  }

  private setMarker(latitude: number, longitude: number, panToMarker = true): void {
    if (!this.map || !this.googleApi) {
      return;
    }

    if (!this.marker) {
      this.marker = new this.googleApi.maps.Marker({
        map: this.map,
        position: { lat: latitude, lng: longitude },
        draggable: !(this.disabled || this.readonly),
      });
      this.marker.addListener('dragend', (event: any) => {
        if (!event?.latLng) {
          return;
        }
        this.applyCoordinates(Number(event.latLng.lat()), Number(event.latLng.lng()), {
          reverseGeocode: true,
          successMessage: 'Location updated from the marker.',
        });
      });
    } else {
      this.marker.setPosition({ lat: latitude, lng: longitude });
      this.marker.setMap(this.map);
      this.marker.setDraggable(!(this.disabled || this.readonly));
    }

    if (panToMarker) {
      this.map.panTo({ lat: latitude, lng: longitude });
      this.map.setZoom(14);
    }
  }

  private applyCoordinates(
    latitude: number,
    longitude: number,
    options: { reverseGeocode?: boolean; successMessage?: string } = {},
  ): void {
    this.onLatitudeInput(formatCoordinateInput(latitude));
    this.onLongitudeInput(formatCoordinateInput(longitude));
    this.setMarker(latitude, longitude);
    if (options.reverseGeocode) {
      this.reverseGeocode(latitude, longitude, options.successMessage);
      return;
    }

    this.mapUrl = buildGoogleMapsLocationUrl(latitude, longitude);
    this.mapUrlChange.emit(this.mapUrl);
    if (options.successMessage) {
      this.pickerMessage = options.successMessage;
    }
  }

  private reverseGeocode(latitude: number, longitude: number, successMessage = 'Location captured.'): void {
    if (!this.geocoder) {
      this.mapUrl = buildGoogleMapsLocationUrl(latitude, longitude);
      this.mapUrlChange.emit(this.mapUrl);
      this.pickerMessage = successMessage;
      return;
    }

    this.geocoder.geocode({ location: { lat: latitude, lng: longitude } }, (results: any[], status: any) => {
      const okStatus = this.googleApi?.maps?.GeocoderStatus?.OK;
      const result = Array.isArray(results) ? results[0] : null;
      if (status !== okStatus || !result) {
        this.mapUrl = buildGoogleMapsLocationUrl(latitude, longitude);
        this.mapUrlChange.emit(this.mapUrl);
        this.pickerMessage = successMessage;
        return;
      }

      const selection = mapGoogleAddressResultToSelection(result, latitude, longitude);
      this.applySelection(selection, false, successMessage);
    });
  }

  private applySelection(selection: GeoLocationSelection, centerMap: boolean, successMessage = 'Location selected from Google Maps.'): void {
    this.onLatitudeInput(selection.latitude);
    this.onLongitudeInput(selection.longitude);
    this.mapUrl = selection.mapUrl;
    this.mapUrlChange.emit(this.mapUrl);
    this.searchQuery = selection.formattedAddress || this.searchQuery;
    this.predictions = [];
    this.locationChange.emit(selection);

    const latitude = Number(selection.latitude);
    const longitude = Number(selection.longitude);
    if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
      this.setMarker(latitude, longitude, centerMap);
    }

    this.pickerError = '';
    this.pickerMessage = successMessage;
  }
}
