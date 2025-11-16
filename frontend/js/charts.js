/**
 * Chart management for DeliriGuard Dashboard
 */

import { CONFIG } from './config.js';

export class ChartManager {
  constructor() {
    this.rmsChart = null;
    this.auxChart = null;
    this.maxPoints = CONFIG.CHART.MAX_POINTS;
  }

  /**
   * Initialize all charts
   */
  init() {
    this.initRMSChart();
    this.initAuxChart();
  }

  /**
   * Initialize RMS movement chart
   */
  initRMSChart() {
    const ctx = document.getElementById('rmsChart');
    if (!ctx) return;

    this.rmsChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Head',
            data: [],
            borderColor: '#60a5fa',
            backgroundColor: 'rgba(96, 165, 250, 0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
          },
          {
            label: 'Body',
            data: [],
            borderColor: '#34d399',
            backgroundColor: 'rgba(52, 211, 153, 0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
          },
          {
            label: 'Leg',
            data: [],
            borderColor: '#f97316',
            backgroundColor: 'rgba(249, 115, 22, 0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
          },
        ],
      },
      options: {
        animation: { duration: CONFIG.CHART.ANIMATION_DURATION },
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: '#f1f5f9' },
            position: 'top',
          },
        },
        scales: {
          x: {
            display: false,
            grid: { color: 'rgba(255, 255, 255, 0.1)' },
          },
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(255, 255, 255, 0.1)' },
            ticks: { color: '#94a3b8' },
          },
        },
      },
    });
  }

  /**
   * Initialize auxiliary (environment) chart
   */
  initAuxChart() {
    const ctx = document.getElementById('auxChart');
    if (!ctx) return;

    this.auxChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Temp (°C)',
            data: [],
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
          },
          {
            label: 'Light',
            data: [],
            borderColor: '#fbbf24',
            backgroundColor: 'rgba(251, 191, 36, 0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
          },
          {
            label: 'Sound RMS',
            data: [],
            borderColor: '#22d3ee',
            backgroundColor: 'rgba(34, 211, 238, 0.1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true,
          },
        ],
      },
      options: {
        animation: { duration: CONFIG.CHART.ANIMATION_DURATION },
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: '#f1f5f9' },
            position: 'top',
          },
        },
        scales: {
          x: {
            display: false,
            grid: { color: 'rgba(255, 255, 255, 0.1)' },
          },
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(255, 255, 255, 0.1)' },
            ticks: { color: '#94a3b8' },
          },
        },
      },
    });
  }

  /**
   * Add data point to RMS chart
   */
  addRMSPoint(head, body, leg) {
    if (!this.rmsChart) return;
    this.addPoint(this.rmsChart, [head, body, leg]);
    this.updatePointCount('pointsA', this.rmsChart.data.labels.length);
  }

  /**
   * Add data point to auxiliary chart
   */
  addAuxPoint(temp, light, sound) {
    if (!this.auxChart) return;
    this.addPoint(this.auxChart, [temp, light, sound]);
    this.updatePointCount('pointsB', this.auxChart.data.labels.length);
  }

  /**
   * Add point to chart
   */
  addPoint(chart, values) {
    chart.data.labels.push('');
    chart.data.datasets.forEach((ds, i) => {
      ds.data.push(Number(values[i]) || 0);
    });

    if (chart.data.labels.length > this.maxPoints) {
      chart.data.labels.shift();
      chart.data.datasets.forEach(ds => ds.data.shift());
    }

    chart.update('none');
  }

  /**
   * Update point count display
   */
  updatePointCount(elementId, count) {
    const el = document.getElementById(elementId);
    if (el) {
      el.textContent = `${count} pts`;
    }
  }

  /**
   * Reset all charts
   */
  reset() {
    if (this.rmsChart) {
      this.rmsChart.data.labels = [];
      this.rmsChart.data.datasets.forEach(ds => ds.data = []);
      this.rmsChart.update();
      this.updatePointCount('pointsA', 0);
    }

    if (this.auxChart) {
      this.auxChart.data.labels = [];
      this.auxChart.data.datasets.forEach(ds => ds.data = []);
      this.auxChart.update();
      this.updatePointCount('pointsB', 0);
    }
  }
}

