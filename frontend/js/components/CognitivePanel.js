/**
 * Cognitive Assessment Panel Component
 */

import { CONFIG } from '../config.js';
import { formatTimestamp, getAlertBadgeClass, getInteractionIcon, getInteractionName } from '../utils.js';

export class CognitivePanel {
  constructor() {
    this.elements = {
      score: document.getElementById('cognitiveScore'),
      alertBadge: document.getElementById('cognitiveAlertBadge'),
      timestamp: document.getElementById('cognitiveTimestamp'),
      orientation: document.getElementById('cognitiveOrientation'),
      memory: document.getElementById('cognitiveMemory'),
      attention: document.getElementById('cognitiveAttention'),
      executive: document.getElementById('cognitiveExecutive'),
      orientationBar: document.getElementById('cognitiveOrientationBar'),
      memoryBar: document.getElementById('cognitiveMemoryBar'),
      attentionBar: document.getElementById('cognitiveAttentionBar'),
      executiveBar: document.getElementById('cognitiveExecutiveBar'),
      scoreRing: document.getElementById('scoreRing'),
      assessmentsList: document.getElementById('assessmentsList'),
      interactionsList: document.getElementById('interactionsList'),
    };

    this.alertColors = ['#10b981', '#f59e0b', '#f59e0b', '#ef4444'];
  }

  /**
   * Update cognitive assessment display
   */
  updateAssessment(assessment) {
    if (!assessment) return;

    const score = assessment.total_score || 0;
    const alertLevel = assessment.alert_level || 0;

    // Update score
    this.elements.score.textContent = score;

    // Update breakdown
    this.elements.orientation.textContent = `${assessment.orientation_score || 0}/3`;
    this.elements.memory.textContent = `${assessment.memory_score || 0}/3`;
    this.elements.attention.textContent = `${assessment.attention_score || 0}/3`;
    this.elements.executive.textContent = `${assessment.executive_score || 0}/3`;

    // Update progress bars
    this.updateProgressBar(this.elements.orientationBar, assessment.orientation_score || 0, 3);
    this.updateProgressBar(this.elements.memoryBar, assessment.memory_score || 0, 3);
    this.updateProgressBar(this.elements.attentionBar, assessment.attention_score || 0, 3);
    this.updateProgressBar(this.elements.executiveBar, assessment.executive_score || 0, 3);

    // Update alert badge
    const alertLabel = CONFIG.ALERT.LABELS[alertLevel] || 'Unknown';
    this.elements.alertBadge.textContent = alertLabel;
    this.elements.alertBadge.className = `badge ${getAlertBadgeClass(alertLevel)}`;

    // Update timestamp
    this.elements.timestamp.textContent = formatTimestamp(assessment.recorded_at);

    // Update score ring
    this.updateScoreRing(score, alertLevel);
  }

  /**
   * Update progress bar
   */
  updateProgressBar(element, value, max) {
    if (!element) return;
    const percentage = (value / max) * 100;
    element.style.width = `${percentage}%`;
    
    // Update color based on value
    if (percentage >= 66) {
      element.style.background = '#10b981';
    } else if (percentage >= 33) {
      element.style.background = '#f59e0b';
    } else {
      element.style.background = '#ef4444';
    }
  }

  /**
   * Update score ring visualization
   */
  updateScoreRing(score, alertLevel) {
    if (!this.elements.scoreRing) return;
    const color = this.alertColors[alertLevel] || this.alertColors[0];
    this.elements.scoreRing.style.border = `4px solid ${color}`;
    this.elements.scoreRing.style.boxShadow = `0 0 20px ${color}40`;
  }

  /**
   * Render assessments list
   */
  renderAssessments(assessments) {
    if (!this.elements.assessmentsList) return;

    if (!assessments || assessments.length === 0) {
      this.elements.assessmentsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state__icon"><i class="fas fa-brain"></i></div>
          <div>No assessments yet</div>
        </div>
      `;
      return;
    }

    this.elements.assessmentsList.innerHTML = assessments.slice().reverse().map(assessment => {
      const date = new Date(assessment.recorded_at);
      const alertLabel = CONFIG.ALERT.LABELS[assessment.alert_level] || 'Unknown';
      const alertClass = getAlertBadgeClass(assessment.alert_level);

      return `
        <div class="card" style="padding: 1rem;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-size: 1.5rem; font-weight: 700;">${assessment.total_score}/12</div>
              <div class="metric__subtitle">${date.toLocaleString()}</div>
            </div>
            <div style="text-align: right;">
              <span class="badge ${alertClass}">${alertLabel}</span>
              <div class="metric__subtitle" style="margin-top: 0.5rem;">
                O:${assessment.orientation_score} M:${assessment.memory_score} A:${assessment.attention_score} E:${assessment.executive_score}
              </div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  /**
   * Render interactions list
   */
  renderInteractions(interactions) {
    if (!this.elements.interactionsList) return;

    if (!interactions || interactions.length === 0) {
      this.elements.interactionsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-state__icon"><i class="fas fa-heart"></i></div>
          <div>No interactions yet</div>
        </div>
      `;
      return;
    }

    this.elements.interactionsList.innerHTML = interactions.slice().reverse().slice(0, 10).map(interaction => {
      const date = new Date(interaction.recorded_at);
      const icon = getInteractionIcon(interaction.interaction_type);
      const name = getInteractionName(interaction.interaction_type);
      const successClass = interaction.success ? 'badge--success' : 'badge--danger';

      return `
        <div class="card" style="padding: 1rem;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-weight: 600;">
                <i class="fas fa-${icon}"></i> ${name}
              </div>
              <div class="metric__subtitle">${date.toLocaleString()}</div>
            </div>
            <div style="text-align: right;">
              <span class="badge ${successClass}">
                ${interaction.success ? 'Success' : 'Failed'}
              </span>
              <div class="metric__subtitle" style="margin-top: 0.5rem;">${interaction.response_time_ms}ms</div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  /**
   * Show loading state
   */
  showLoading() {
    if (this.elements.assessmentsList) {
      this.elements.assessmentsList.innerHTML = `
        <div class="loading">
          <div class="loading__spinner"><i class="fas fa-spinner"></i></div>
          <div>Loading assessments...</div>
        </div>
      `;
    }

    if (this.elements.interactionsList) {
      this.elements.interactionsList.innerHTML = `
        <div class="loading">
          <div class="loading__spinner"><i class="fas fa-spinner"></i></div>
          <div>Loading interactions...</div>
        </div>
      `;
    }
  }
}

