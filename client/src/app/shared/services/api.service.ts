import { Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { HTTP_LOADING_MODE, HTTP_LOADING_SCOPE, HttpLoadingMode } from '../http/http-loading.tokens';

export interface ApiRequestOptions {
  params?: HttpParams;
  headers?: HttpHeaders;
  loadingMode?: HttpLoadingMode;
  loadingScope?: string;
}

@Injectable({providedIn: 'root'})
export class ApiService {
  private baseUrl = '/api';

  constructor(private http: HttpClient) {}

  get<T>(endpoint: string, options?: ApiRequestOptions): Observable<T> {
    return this.http.get<T>(`${this.baseUrl}/${endpoint}`, this.buildOptions(options));
  }

  post<T>(endpoint: string, body: any, options?: ApiRequestOptions): Observable<T> {
    return this.http.post<T>(`${this.baseUrl}/${endpoint}`, body, this.buildOptions(options));
  }

  put<T>(endpoint: string, body: any, options?: ApiRequestOptions): Observable<T> {
    return this.http.put<T>(`${this.baseUrl}/${endpoint}`, body, this.buildOptions(options));
  }

  patch<T>(endpoint: string, body?: any, options?: ApiRequestOptions): Observable<T> {
    return this.http.patch<T>(`${this.baseUrl}/${endpoint}`, body || {}, this.buildOptions(options));
  }

  delete<T>(endpoint: string, options?: ApiRequestOptions): Observable<T> {
    return this.http.delete<T>(`${this.baseUrl}/${endpoint}`, this.buildOptions(options));
  }

  private buildOptions(options?: ApiRequestOptions): { params?: HttpParams; headers?: HttpHeaders; context: HttpContext } {
    let context = new HttpContext();

    if (options?.loadingMode) {
      context = context.set(HTTP_LOADING_MODE, options.loadingMode);
    }
    if (options?.loadingScope) {
      context = context.set(HTTP_LOADING_SCOPE, options.loadingScope);
    }

    return {
      params: options?.params,
      headers: options?.headers,
      context,
    };
  }
}
