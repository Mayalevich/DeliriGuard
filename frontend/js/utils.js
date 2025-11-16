/**
 * Utility functions for DeliriGuard Dashboard
 */

import { CONFIG } from './config.js';

/**
 * Format timestamp to readable string
 */
export function formatTimestamp(timestamp) {
  if (!timestamp) return 'N/A';
  const date = new Date(timestamp);
  return date.toLocaleString();
}

/**
 * Format time duration
 */
export function formatDuration(seconds) {
  if (isNaN(seconds)) return '0.0 s';
  return `${Number(seconds).toFixed(1)} s`;
}

/**
 * Get activity badge class
 */
export function getActivityBadgeClass(level) {
  const classes = ['badge--success', 'badge--warning', 'badge--danger'];
  return classes[Math.max(0, Math.min(2, Number(level) || 0))] || 'badge--info';
}

/**
 * Get alert badge class
 */
export function getAlertBadgeClass(level) {
  const classes = ['badge--success', 'badge--warning', 'badge--warning', 'badge--danger'];
  return classes[Math.max(0, Math.min(3, Number(level) || 0))] || 'badge--info';
}

/**
 * Describe sleep score
 */
export function describeSleepScore(score) {
  if (score >= CONFIG.SLEEP_SCORE.EXCELLENT) return 'Excellent rest';
  if (score >= CONFIG.SLEEP_SCORE.GOOD) return 'Generally restful';
  if (score >= CONFIG.SLEEP_SCORE.FAIR) return 'Watch for disturbances';
  return 'High movement detected';
}

/**
 * Calculate delirium risk from sleep and cognitive scores
 */
export function calculateRiskLevel(sleepScore, cognitiveScore, cognitiveAlertLevel) {
  // High risk if either is concerning
  if (sleepScore < 50 || cognitiveAlertLevel >= 2) {
    return { level: 'High', class: 'badge--danger' };
  }
  if (sleepScore < 70 || cognitiveAlertLevel === 1) {
    return { level: 'Moderate', class: 'badge--warning' };
  }
  return { level: 'Low', class: 'badge--success' };
}

/**
 * Build WebSocket URL
 */
export function buildWebSocketUrl() {
  if (window.location.protocol.startsWith('http')) {
    const isSecure = window.location.protocol === 'https:';
    const proto = isSecure ? 'wss' : 'ws';
    const host = window.location.hostname || 'localhost';
    const port = window.location.port || (isSecure ? '443' : '8000');
    return `${proto}://${host}:${port}${CONFIG.API.WEBSOCKET}`;
  }
  return `ws://localhost:8000${CONFIG.API.WEBSOCKET}`;
}

/**
 * Debounce function
 */
export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * Format number with precision
 */
export function formatNumber(value, precision = 1) {
  if (isNaN(value)) return '–';
  return Number(value).toFixed(precision);
}

/**
 * Get interaction icon
 */
export function getInteractionIcon(type) {
  const icons = {
    0: 'utensils',      // feed
    1: 'gamepad',       // play
    2: 'soap',          // clean
    3: 'puzzle-piece',  // game
  };
  return icons[type] || 'circle';
}

/**
 * Get interaction name
 */
export function getInteractionName(type) {
  const names = ['Feed', 'Play', 'Clean', 'Game'];
  return names[type] || 'Unknown';
}

