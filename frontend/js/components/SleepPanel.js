/**
 * Sleep Monitoring Panel Component
 */

import { CONFIG } from '../config.js';
import { formatDuration, getActivityBadgeClass, describeSleepScore } from '../utils.js';

export class SleepPanel {
  constructor() {
    this.elements = {
      score: document.getElementById('scoreVal'),
      rmsH: document.getElementById('rmsH'),
      rmsB: document.getElementById('rmsB'),
      rmsL: document.getElementById('rmsL'),
      movH: document.getElementById('movH'),
      movB: document.getElementById('movB'),
      movL: document.getElementById('movL'),
      time: document.getElementById('timeVal'),
      evSec: document.getElementById('evSec'),
      evMin: document.getElementById('evMin'),
    };
  }

  /**
   * Update sleep data display
   */
  update(payload) {
    if (!payload) return;

    // Update values
    this.elements.score.textContent = Number(payload.SleepScore || 0).toFixed(0);
    this.elements.rmsH.textContent = Number(payload.RMS_H || 0).toFixed(1);
    this.elements.rmsB.textContent = Number(payload.RMS_B || 0).toFixed(1);
    this.elements.rmsL.textContent = Number(payload.RMS_L || 0).toFixed(1);
    this.elements.time.textContent = formatDuration(payload.time_s);

    // Update activity badges
    this.updateBadge(this.elements.movH, payload.activity_H);
    this.updateBadge(this.elements.movB, payload.activity_B);
    this.updateBadge(this.elements.movL, payload.activity_L);

    // Update events
    const secH = Number(payload.secEv_H) || 0;
    const secB = Number(payload.secEv_B) || 0;
    const secL = Number(payload.secEv_L) || 0;
    const minH = Number(payload.minute_events_H) || 0;
    const minB = Number(payload.minute_events_B) || 0;
    const minL = Number(payload.minute_events_L) || 0;

    this.elements.evSec.textContent = `H${secH} / B${secB} / L${secL}`;
    this.elements.evMin.textContent = `H${minH} / B${minB} / L${minL}`;
  }

  /**
   * Update activity badge
   */
  updateBadge(element, level) {
    if (!element) return;
    const levelNum = Math.max(0, Math.min(2, Number(level) || 0));
    element.textContent = CONFIG.ACTIVITY.LABELS[levelNum] || 'Idle';
    element.className = `badge ${getActivityBadgeClass(levelNum)}`;
  }

  /**
   * Reset display
   */
  reset() {
    this.elements.score.textContent = '100';
    this.elements.rmsH.textContent = '0.0';
    this.elements.rmsB.textContent = '0.0';
    this.elements.rmsL.textContent = '0.0';
    this.elements.time.textContent = '0.0 s';
    this.elements.evSec.textContent = 'H0 / B0 / L0';
    this.elements.evMin.textContent = 'H0 / B0 / L0';
    this.updateBadge(this.elements.movH, 0);
    this.updateBadge(this.elements.movB, 0);
    this.updateBadge(this.elements.movL, 0);
  }
}

