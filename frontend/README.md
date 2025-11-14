# NightWatch Frontend

Professional, modular frontend for the NightWatch Delirium Detection Dashboard.

## Structure

```
frontend/
├── index.html          # Main HTML entry point
├── css/
│   └── main.css        # Main stylesheet with CSS variables and components
├── js/
│   ├── app.js          # Main application controller
│   ├── config.js       # Configuration constants
│   ├── utils.js        # Utility functions
│   ├── api.js          # API client
│   ├── charts.js       # Chart management
│   ├── websocket.js    # WebSocket connection manager
│   └── components/
│       ├── SleepPanel.js       # Sleep monitoring panel component
│       ├── CognitivePanel.js   # Cognitive assessment panel component
│       └── OverviewPanel.js    # Overview panel component
```

## Architecture

### Modular Design
- **Separation of Concerns**: Each component handles its own logic
- **ES6 Modules**: Modern JavaScript with import/export
- **Component-Based**: Reusable panel components
- **Configuration-Driven**: Centralized config for easy customization

### Key Features

1. **Component System**
   - `SleepPanel`: Handles sleep monitoring data display
   - `CognitivePanel`: Manages cognitive assessment visualization
   - `OverviewPanel`: Combined overview of all metrics

2. **Chart Management**
   - `ChartManager`: Centralized chart initialization and updates
   - Real-time data streaming
   - Efficient point management with max limits

3. **WebSocket Integration**
   - Auto-reconnect logic
   - Connection status management
   - Message handling and routing

4. **API Client**
   - Centralized API calls
   - Error handling
   - Promise-based async operations

5. **Styling**
   - CSS Variables for theming
   - Responsive design
   - Modern dark theme
   - Smooth animations and transitions

## Development

The frontend uses ES6 modules, so it requires a server to run (cannot use `file://` protocol).

### Local Development

1. Start the FastAPI backend server
2. Navigate to `http://localhost:8000`
3. The frontend will be served automatically

### Building

No build step required - the frontend uses vanilla JavaScript ES6 modules that are supported by modern browsers.

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

Requires ES6 module support (all modern browsers).

