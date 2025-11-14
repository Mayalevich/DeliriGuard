/**
 * Overview Panel Component
 */

import { CONFIG } from '../config.js';
import { formatDuration, getActivityBadgeClass, describeSleepScore, calculateRiskLevel } from '../utils.js';

export class OverviewPanel {
  constructor() {
    this.elements = {
      score: document.getElementById('overviewScore'),
      scoreHint: document.getElementById('overviewScoreHint'),
      rest: document.getElementById('overviewRest'),
      restBadge: document.getElementById('overviewRestBadge'),
      restHint: document.getElementById('overviewRestHint'),
      movement: document.getElementById('overviewMovement'),
      envTemp: document.getElementById('overviewEnvironmentTemp'),
      envLight: document.getElementById('overviewEnvironmentLight'),
      envSound: document.getElementById('overviewEnvironmentSound'),
      monitoring: document.getElementById('overviewMonitoring'),
      monitoringHint: document.getElementById('overviewMonitoringHint'),
      time: document.getElementById('overviewTime'),
      events: document.getElementById('overviewEvents'),
      cognitiveScore: document.getElementById('overviewCognitiveScore'),
      cognitiveAlert: document.getElementById('overviewCognitiveAlert'),
      risk: document.getElementById('overviewRisk'),
    };

    this.hints = [
      'Body appears calm.',
      'Minor movement detected — continue to observe.',
      'Significant movement detected — check patient.',
    ];
  }

  /**
   * Update overview with sleep data
   */
  updateSleep(payload) {
    if (!payload) return;

    const score = Number(payload.SleepScore || 0);
    this.elements.score.textContent = score.toFixed(0);
    this.elements.scoreHint.textContent = describeSleepScore(score);

    const headLevel = Number(payload.activity_H) || 0;
    const bodyLevel = Number(payload.activity_B) || 0;
    const legLevel = Number(payload.activity_L) || 0;
    const overallLevel = Number(payload.status_level) || Math.max(headLevel, bodyLevel, legLevel);
    const overallLabel = payload.status_label || CONFIG.ACTIVITY.LABELS[overallLevel] || 'Idle';

    this.elements.rest.textContent = overallLabel;
    this.elements.restBadge.textContent = overallLabel;
    this.elements.restBadge.className = `badge ${getActivityBadgeClass(overallLevel)}`;
    this.elements.restHint.textContent = this.hints[overallLevel] || this.hints[0];

    this.elements.movement.textContent = 
      `Head ${CONFIG.ACTIVITY.LABELS[headLevel]} · Body ${CONFIG.ACTIVITY.LABELS[bodyLevel]} · Leg ${CONFIG.ACTIVITY.LABELS[legLevel]}`;

    const temp = Number(payload.TempC);
    const light = Number(payload.LightRaw);
    const sound = Number(payload.SoundRMS);

    this.elements.envTemp.textContent = `${isNaN(temp) ? '–' : temp.toFixed(1)} °C`;
    this.elements.envLight.textContent = `${isNaN(light) ? '–' : light.toFixed(0)}`;
    this.elements.envSound.textContent = `${isNaN(sound) ? '–' : sound.toFixed(1)}`;

    const monitoring = Number(payload.monitoring) === 1 || payload.monitoring === true;
    this.elements.monitoring.textContent = monitoring ? 'Active' : 'Paused';
    this.elements.monitoringHint.textContent = monitoring ? 'System monitoring' : 'Monitoring paused';

    this.elements.time.textContent = formatDuration(payload.time_s);
    this.elements.events.textContent = 
      `H${payload.minute_events_H || 0} · B${payload.minute_events_B || 0} · L${payload.minute_events_L || 0}`;
  }

  /**
   * Update overview with cognitive data
   */
  updateCognitive(assessment) {
    if (!assessment) {
      this.elements.cognitiveScore.textContent = '–';
      this.elements.cognitiveAlert.textContent = 'No data';
      return;
    }

    const score = assessment.total_score || 0;
    const alertLevel = assessment.alert_level || 0;
    const alertLabel = CONFIG.ALERT.LABELS[alertLevel] || 'Unknown';

    this.elements.cognitiveScore.textContent = `${score}/12`;
    this.elements.cognitiveAlert.textContent = alertLabel;
  }

  /**
   * Update risk assessment
   */
  updateRisk(sleepScore, cognitiveScore, cognitiveAlertLevel) {
    if (!this.elements.risk) return;

    const risk = calculateRiskLevel(sleepScore, cognitiveScore, cognitiveAlertLevel);
    this.elements.risk.textContent = risk.level;
    this.elements.risk.className = `metric__value ${risk.class}`;
  }

  /**
   * Reset display
   */
  reset() {
    this.elements.score.textContent = '–';
    this.elements.scoreHint.textContent = 'Awaiting data…';
    this.elements.rest.textContent = 'Calm';
    this.elements.restBadge.textContent = 'Calm';
    this.elements.restBadge.className = 'badge badge--success';
    this.elements.restHint.textContent = 'No data yet.';
    this.elements.movement.textContent = 'Head – · Body – · Leg –';
    this.elements.envTemp.textContent = '– °C';
    this.elements.envLight.textContent = '–';
    this.elements.envSound.textContent = '–';
    this.elements.monitoring.textContent = 'Active';
    this.elements.monitoringHint.textContent = 'System monitoring';
    this.elements.time.textContent = '0.0 s';
    this.elements.events.textContent = 'H0 · B0 · L0';
    this.elements.cognitiveScore.textContent = '–';
    this.elements.cognitiveAlert.textContent = 'No data';
    this.elements.risk.textContent = 'Low';
    this.elements.risk.className = 'metric__value badge--success';
  }
}

