/**
 * API client for DeliriGuard Dashboard
 */

import { CONFIG } from './config.js';

export class APIClient {
  constructor() {
    this.baseURL = CONFIG.API.BASE_URL;
  }

  /**
   * Fetch with error handling
   */
  async fetch(endpoint, options = {}) {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error (${endpoint}):`, error);
      throw error;
    }
  }

  /**
   * Get sleep history
   */
  async getHistory(limit = CONFIG.CHART.MAX_POINTS) {
    return this.fetch(`${CONFIG.API.HISTORY}?limit=${limit}`);
  }

  /**
   * Get latest sleep sample
   */
  async getLatest() {
    return this.fetch(CONFIG.API.LATEST);
  }

  /**
   * Get system status
   */
  async getStatus() {
    return this.fetch(CONFIG.API.STATUS);
  }

  /**
   * Reset system
   */
  async reset() {
    return this.fetch(CONFIG.API.RESET, { method: 'POST' });
  }

  /**
   * Get cognitive assessments
   */
  async getAssessments(limit = 100) {
    return this.fetch(`${CONFIG.API.ASSESSMENTS}?limit=${limit}`);
  }

  /**
   * Get pet interactions
   */
  async getInteractions(limit = 200) {
    return this.fetch(`${CONFIG.API.INTERACTIONS}?limit=${limit}`);
  }
}

