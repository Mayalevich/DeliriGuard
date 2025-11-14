/**
 * WebSocket connection manager
 */

import { buildWebSocketUrl } from './utils.js';

export class WebSocketManager {
  constructor(onMessage, onStatusChange) {
    this.socket = null;
    this.url = buildWebSocketUrl();
    this.onMessage = onMessage;
    this.onStatusChange = onStatusChange;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;
  }

  /**
   * Connect to WebSocket
   */
  connect() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.disconnect();
      return;
    }

    try {
      this.socket = new WebSocket(this.url);

      this.socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.onStatusChange(true);
        if (this.onMessage) {
          this.onMessage({ type: 'status', message: 'Connected' });
        }
      };

      this.socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (this.onMessage) {
            this.onMessage(msg);
          }
        } catch (err) {
          console.error('WebSocket message parse error:', err);
          if (this.onMessage) {
            this.onMessage({ type: 'error', message: 'Failed to parse message' });
          }
        }
      };

      this.socket.onclose = () => {
        this.onStatusChange(false);
        if (this.onMessage) {
          this.onMessage({ type: 'status', message: 'Disconnected' });
        }
        this.attemptReconnect();
      };

      this.socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        if (this.onMessage) {
          this.onMessage({ type: 'error', message: 'WebSocket error occurred' });
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      if (this.onMessage) {
        this.onMessage({ type: 'error', message: 'Failed to connect' });
      }
    }
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  /**
   * Attempt to reconnect
   */
  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        if (this.onMessage) {
          this.onMessage({ type: 'status', message: `Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})` });
        }
        this.connect();
      }, this.reconnectDelay);
    }
  }

  /**
   * Check if connected
   */
  isConnected() {
    return this.socket && this.socket.readyState === WebSocket.OPEN;
  }
}

