import asyncio
import csv
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import serial
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import io

import plotly.graph_objs as go
import plotly.io as pio
from plotly.subplots import make_subplots

from .pipeline import RawSample, SleepPipeline
from . import database
from .posture_detection import PostureDetectionService, CV2_AVAILABLE
from .camera_stream import get_camera_stream

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("sleep-backend")


class BroadcastHub:
  def __init__(self) -> None:
    self.queues: List[asyncio.Queue] = []
    self._lock = asyncio.Lock()

  async def register(self) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    async with self._lock:
      self.queues.append(queue)
    return queue

  async def unregister(self, queue: asyncio.Queue) -> None:
    async with self._lock:
      if queue in self.queues:
        self.queues.remove(queue)

  async def publish(self, message: Dict) -> None:
    async with self._lock:
      queues = list(self.queues)
    for queue in queues:
      if queue.full():
        try:
          queue.get_nowait()
        except asyncio.QueueEmpty:
          pass
      await queue.put(message)


class SerialReader:
  def __init__(self, port: str, baud: int = 115200) -> None:
    self.port = port
    self.baud = baud
    self._serial: Optional[serial.Serial] = None

  def open(self) -> None:
    if self._serial and self._serial.is_open:
      return
    logger.info("Opening serial port %s", self.port)
    self._serial = serial.Serial(self.port, self.baud, timeout=1)
    self._serial.reset_input_buffer()
    time.sleep(0.1)

  def readline(self) -> Optional[str]:
    if not self._serial:
      return None
    while True:
      try:
        raw = self._serial.readline()
      except serial.SerialException as exc:
        logger.debug("Serial transient: %s", exc)
        return None
      if not raw:
        return None
      decoded = raw.decode("utf-8", errors="ignore").strip()
      if decoded:
        return decoded

  def close(self) -> None:
    if self._serial and self._serial.is_open:
      logger.info("Closing serial port")
      self._serial.close()


class BackendService:
  def __init__(self, port: str, posture_service=None) -> None:
    self.pipeline = SleepPipeline(posture_service=posture_service)
    self.reader = SerialReader(port)
    self.hub = BroadcastHub()
    self._task: Optional[asyncio.Task] = None
    self._running = False

  async def start(self) -> None:
    if self._task and not self._task.done():
      return
    self._running = True
    loop = asyncio.get_running_loop()
    self.reader.open()
    self._task = loop.create_task(self._run())

  async def stop(self) -> None:
    self._running = False
    if self._task:
      await self._task
    self.reader.close()

  async def reset(self) -> None:
    self.pipeline = SleepPipeline()
    await asyncio.to_thread(database.clear_samples)
    await self.hub.publish({"type": "status", "message": "reset"})

  async def _run(self) -> None:
    header_seen = False
    while self._running:
      line = await asyncio.to_thread(self.reader.readline)
      if not line:
        continue
      logger.info("Serial line: %s", line)
      if not header_seen:
        if line.startswith("time_ms"):
          header_seen = True
          logger.debug("CSV header detected")
          continue
      sample = self._parse_sample(line)
      if not sample:
        logger.warning("Failed to parse sample from line: %s", line)
        continue
      logger.debug("Parsed sample: time_ms=%d", sample.time_ms)
      events = self.pipeline.process_sample(sample)
      logger.debug("Pipeline returned %d events", len(events))
      for event in events:
        if event.get("type") == "data":
          processed = event["payload"]
          logger.info("Saving processed sample: time_s=%.1f", processed.time_s)
          await asyncio.to_thread(database.save_processed_sample, processed)
          logger.info("Sample saved to database")
        await self.hub.publish(event)

  def _parse_sample(self, line: str) -> Optional[RawSample]:
    try:
      parts = next(csv.reader([line]))
      if len(parts) < 8:
        return None
      time_ms = int(parts[0])
      piezo = {
        "head": int(parts[1]),
        "body": int(parts[2]),
        "leg": int(parts[3]),
      }
      sound = int(parts[4])
      light = int(parts[5])
      temp = int(parts[6])
      button = int(parts[7])
      return RawSample(
        time_ms=time_ms,
        piezo=piezo,
        sound=sound,
        light=light,
        temp_raw=temp,
        button=button,
      )
    except (ValueError, csv.Error) as exc:
      logger.warning("Failed to parse line '%s': %s", line, exc)
      return None


SERIAL_PORT = os.environ.get("SLEEP_SERIAL_PORT", "/dev/tty.usbmodem1101")

# Initialize posture detection service (optional, will be disabled if model not available)
posture_service = PostureDetectionService(
    video_source=os.environ.get("POSTURE_VIDEO_SOURCE", "0"),  # 0 = default camera
    confidence_threshold=float(os.environ.get("POSTURE_CONFIDENCE", "0.5")),
    process_interval=float(os.environ.get("POSTURE_INTERVAL", "1.0")),  # Process every 1 second
)

# Initialize backend service with posture service reference
service = BackendService(SERIAL_PORT, posture_service=posture_service)
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DASHBOARD_PATH = PROJECT_ROOT / "frontend" / "index.html"
PATIENTS_PATH = PROJECT_ROOT / "frontend" / "patients.html"
FRONTEND_STATIC = PROJECT_ROOT / "frontend"
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Sleep Monitor Backend", version="1.0.0")
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# Mount static files (CSS, JS, etc.) - must be before route definitions
if FRONTEND_STATIC.exists():
  app.mount("/static", StaticFiles(directory=str(FRONTEND_STATIC)), name="static")


@app.on_event("startup")
async def startup_event() -> None:
  database.init_db()
  try:
    await service.start()
  except Exception as exc:  # pragma: no cover
    logger.error("Failed to start backend service: %s", exc)
  
  # Start posture detection service if available
  try:
    await posture_service.start()
    logger.info("Posture detection service started")
  except Exception as exc:
    logger.warning("Posture detection service not available: %s", exc)


@app.on_event("shutdown")
async def shutdown_event() -> None:
  await service.stop()
  await posture_service.stop()


@app.get("/status")
async def status() -> JSONResponse:
  latest = await asyncio.to_thread(database.get_latest_sample)
  total_rows = await asyncio.to_thread(database.count_samples)
  body = {
    "monitoring": service.pipeline.monitoring,
    "calibrating": service.pipeline.calibrating,
    "serial_port": SERIAL_PORT,
    "rows_recorded": total_rows,
    "latest": latest,
  }
  return JSONResponse(body)


@app.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
  await websocket.accept()
  queue = await service.hub.register()
  try:
    while True:
      event = await queue.get()
      if event.get("type") == "data":
        payload = event["payload"].to_dict()
        await websocket.send_text(json.dumps({"type": "data", "payload": payload}))
      elif event.get("type") == "status":
        await websocket.send_text(json.dumps(event))
  except WebSocketDisconnect:
    logger.info("WebSocket disconnected")
  finally:
    await service.hub.unregister(queue)


@app.get("/")
async def index() -> FileResponse:
  return FileResponse(DASHBOARD_PATH)


@app.get("/patients")
async def patients_portal() -> FileResponse:
  return FileResponse(PATIENTS_PATH)


@app.get("/api/history")
async def history(limit: int = 300, minutes: Optional[int] = None) -> JSONResponse:
  if minutes is not None and minutes > 0:
    data = await asyncio.to_thread(database.get_samples_since, minutes)
  else:
    data = await asyncio.to_thread(database.get_recent_samples, max(1, min(limit, 2000)))
  return JSONResponse(data)


@app.get("/api/latest")
async def latest() -> JSONResponse:
  data = await asyncio.to_thread(database.get_latest_sample)
  if data is None:
    return JSONResponse({}, status_code=204)
  return JSONResponse(data)


@app.post("/api/reset")
async def reset() -> JSONResponse:
  await service.reset()
  return JSONResponse({"status": "reset"})


@app.post("/api/cognitive-assessment")
async def receive_assessment(payload: dict) -> JSONResponse:
  """Receive cognitive assessment data from CogniPet device via BLE bridge"""
  try:
    await asyncio.to_thread(
      database.save_cognitive_assessment,
      device_timestamp_ms=int(payload.get("device_timestamp_ms", 0)),
      orientation_score=int(payload.get("orientation_score", 0)),
      memory_score=int(payload.get("memory_score", 0)),
      attention_score=int(payload.get("attention_score", 0)),
      executive_score=int(payload.get("executive_score", 0)),
      total_score=int(payload.get("total_score", 0)),
      avg_response_time_ms=int(payload.get("avg_response_time_ms", 0)),
      alert_level=int(payload.get("alert_level", 0)),
    )
    return JSONResponse({"status": "received", "message": "Assessment saved"})
  except Exception as e:
    return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


@app.post("/api/pet-interaction")
async def receive_interaction(payload: dict) -> JSONResponse:
  """Receive pet interaction data from CogniPet device via BLE bridge"""
  try:
    mood = payload.get("mood_selected")
    await asyncio.to_thread(
      database.save_pet_interaction,
      device_timestamp_ms=int(payload.get("device_timestamp_ms", 0)),
      interaction_type=int(payload.get("interaction_type", 0)),
      response_time_ms=int(payload.get("response_time_ms", 0)),
      success=bool(payload.get("success", False)),
      mood_selected=int(mood) if mood is not None and mood >= 0 else None,
    )
    return JSONResponse({"status": "received", "message": "Interaction saved"})
  except Exception as e:
    return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


@app.get("/api/assessments")
async def get_assessments(limit: int = 100) -> JSONResponse:
  """Get recent cognitive assessments"""
  data = await asyncio.to_thread(database.get_recent_assessments, limit)
  return JSONResponse(data)


@app.get("/api/interactions")
async def get_interactions(limit: int = 200) -> JSONResponse:
  """Get recent pet interactions"""
  data = await asyncio.to_thread(database.get_recent_interactions, limit)
  return JSONResponse(data)


@app.get("/api/posture/current")
async def get_current_posture() -> JSONResponse:
  """Get current posture detection"""
  posture = posture_service.get_current_posture()
  if posture is None:
    return JSONResponse({"status": "no_detection", "message": "No posture detected yet"}, status_code=204)
  return JSONResponse(posture)


@app.get("/api/posture/history")
async def get_posture_history(limit: int = 200, minutes: Optional[int] = None) -> JSONResponse:
  """Get recent posture detection history"""
  if minutes is not None and minutes > 0:
    data = await asyncio.to_thread(database.get_posture_detections_since, minutes)
  else:
    data = await asyncio.to_thread(database.get_recent_posture_detections, max(1, min(limit, 1000)))
  return JSONResponse(data)


@app.get("/api/posture/latest")
async def get_latest_posture() -> JSONResponse:
  """Get latest posture detection from database"""
  data = await asyncio.to_thread(database.get_latest_posture_detection)
  if data is None:
    return JSONResponse({"status": "no_data"}, status_code=204)
  return JSONResponse(data)


@app.get("/api/posture/statistics")
async def get_posture_statistics() -> JSONResponse:
  """Get posture detection statistics"""
  stats = posture_service.get_posture_statistics()
  return JSONResponse(stats)


@app.post("/api/posture/start")
async def start_posture_detection() -> JSONResponse:
  """Start posture detection service"""
  try:
    await posture_service.start()
    return JSONResponse({"status": "started", "message": "Posture detection started"})
  except Exception as e:
    return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


@app.post("/api/posture/stop")
async def stop_posture_detection() -> JSONResponse:
  """Stop posture detection service"""
  try:
    await posture_service.stop()
    return JSONResponse({"status": "stopped", "message": "Posture detection stopped"})
  except Exception as e:
    return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


@app.get("/api/posture/status")
async def get_posture_status() -> JSONResponse:
  """Get detailed posture detection status"""
  status = {
    "service_running": posture_service.running,
    "detector_initialized": posture_service.detector.initialized,
    "video_source": posture_service.video_source,
    "camera_opened": posture_service.cap is not None and posture_service.cap.isOpened() if posture_service.cap else False,
    "total_detections": posture_service.total_detections,
    "last_detection": posture_service.last_detection,
  }
  
  # Check if camera is accessible
  if CV2_AVAILABLE:
    try:
      import cv2
      test_cap = cv2.VideoCapture(int(posture_service.video_source) if posture_service.video_source.isdigit() else posture_service.video_source)
      status["camera_accessible"] = test_cap.isOpened()
      if test_cap.isOpened():
        ret, _ = test_cap.read()
        status["camera_reading"] = ret
      test_cap.release()
    except:
      status["camera_accessible"] = False
  else:
    status["camera_accessible"] = False
    status["opencv_available"] = False
  
  return JSONResponse(status)


def generate_camera_frames():
    """Generate camera frames for streaming"""
    import cv2
    stream = get_camera_stream(posture_service.video_source)
    
    if not stream.running:
        if not stream.start():
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + 
                   b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00' +
                   b'\r\n')
            return
    
    frame_count = 0
    while stream.running:
        frame = stream.read_frame()
        if frame is None:
            import time
            time.sleep(0.1)
            continue
        
        frame_count += 1
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue
        
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Small delay to control frame rate
        import time
        time.sleep(0.033)  # ~30 FPS


@app.get("/api/camera/stream")
async def camera_stream():
    """Stream camera feed as MJPEG"""
    if not CV2_AVAILABLE:
        return JSONResponse({"error": "OpenCV not available"}, status_code=503)
    
    return StreamingResponse(
        generate_camera_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/camera")
async def camera_preview() -> HTMLResponse:
    """Camera preview page"""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Camera Preview - Posture Detection</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #f1f5f9;
            padding: 2rem;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            margin-bottom: 2rem;
        }
        .header h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        .header p {
            color: #94a3b8;
        }
        .camera-container {
            background: #1e293b;
            border-radius: 0.75rem;
            padding: 1rem;
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.4);
        }
        .camera-feed {
            width: 100%;
            max-width: 1280px;
            height: auto;
            border-radius: 0.5rem;
            background: #000;
        }
        .status-bar {
            display: flex;
            gap: 2rem;
            margin-top: 1rem;
            padding: 1rem;
            background: #334155;
            border-radius: 0.5rem;
        }
        .status-item {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }
        .status-label {
            font-size: 0.75rem;
            color: #94a3b8;
            text-transform: uppercase;
        }
        .status-value {
            font-size: 1.25rem;
            font-weight: 600;
        }
        .status-value.success {
            color: #10b981;
        }
        .status-value.error {
            color: #ef4444;
        }
        .controls {
            margin-top: 1rem;
            display: flex;
            gap: 1rem;
        }
        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 0.5rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #4f46e5;
            color: white;
        }
        .btn-primary:hover {
            background: #4338ca;
        }
        .btn-secondary {
            background: #64748b;
            color: white;
        }
        .btn-secondary:hover {
            background: #475569;
        }
        .error-message {
            padding: 1rem;
            background: #7f1d1d;
            border: 1px solid #ef4444;
            border-radius: 0.5rem;
            color: #fca5a5;
            margin-top: 1rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📹 Camera Preview</h1>
            <p>Live camera feed for posture detection debugging</p>
        </div>
        
        <div class="camera-container">
            <img id="cameraFeed" class="camera-feed" src="/api/camera/stream" alt="Camera Feed">
            
            <div class="status-bar" id="statusBar">
                <div class="status-item">
                    <div class="status-label">Camera Status</div>
                    <div class="status-value" id="cameraStatus">Loading...</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Resolution</div>
                    <div class="status-value" id="resolution">—</div>
                </div>
                <div class="status-item">
                    <div class="status-label">FPS</div>
                    <div class="status-value" id="fps">—</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Detections</div>
                    <div class="status-value" id="detections">0</div>
                </div>
            </div>
            
            <div class="controls">
                <button class="btn btn-primary" onclick="refreshStream()">🔄 Refresh Stream</button>
                <button class="btn btn-secondary" onclick="checkStatus()">📊 Check Status</button>
                <a href="/" class="btn btn-secondary" style="text-decoration: none; display: inline-block;">← Back to Dashboard</a>
            </div>
            
            <div id="errorMessage" style="display: none;" class="error-message"></div>
        </div>
    </div>
    
    <script>
        let statusCheckInterval;
        
        function updateStatus() {
            fetch('/api/posture/status')
                .then(r => r.json())
                .then(data => {
                    const statusEl = document.getElementById('cameraStatus');
                    const resolutionEl = document.getElementById('resolution');
                    const fpsEl = document.getElementById('fps');
                    const detectionsEl = document.getElementById('detections');
                    const errorEl = document.getElementById('errorMessage');
                    
                    if (data.camera_opened || data.camera_accessible) {
                        statusEl.textContent = '✓ Active';
                        statusEl.className = 'status-value success';
                        errorEl.style.display = 'none';
                    } else {
                        statusEl.textContent = '✗ Inactive';
                        statusEl.className = 'status-value error';
                        errorEl.style.display = 'block';
                        errorEl.textContent = 'Camera is not accessible. Check permissions and ensure no other app is using the camera.';
                    }
                    
                    if (data.camera_info) {
                        resolutionEl.textContent = `${data.camera_info.width}x${data.camera_info.height}`;
                        fpsEl.textContent = data.camera_info.fps.toFixed(1);
                    } else if (data.camera_test_resolution) {
                        resolutionEl.textContent = data.camera_test_resolution;
                    }
                    
                    detectionsEl.textContent = data.total_detections || 0;
                })
                .catch(err => {
                    console.error('Status check failed:', err);
                });
        }
        
        function refreshStream() {
            const img = document.getElementById('cameraFeed');
            const src = img.src;
            img.src = '';
            setTimeout(() => {
                img.src = src + '?t=' + Date.now();
            }, 100);
        }
        
        function checkStatus() {
            updateStatus();
        }
        
        // Check status every 5 seconds
        statusCheckInterval = setInterval(updateStatus, 5000);
        
        // Initial status check
        updateStatus();
        
        // Handle image load errors
        document.getElementById('cameraFeed').onerror = function() {
            const errorEl = document.getElementById('errorMessage');
            errorEl.style.display = 'block';
            errorEl.textContent = 'Failed to load camera stream. Make sure the camera is accessible and permissions are granted.';
        };
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


def _parse_timestamp(payload: Dict) -> datetime:
  raw = payload.get("recorded_at")
  if raw:
    try:
      return datetime.fromisoformat(raw)
    except ValueError:
      pass
  return datetime.now(timezone.utc)


def _score_hint(score: float) -> str:
  if score >= 85:
    return "Excellent rest"
  if score >= 70:
    return "Generally restful"
  if score >= 50:
    return "Monitor for restlessness"
  return "High movement detected"


def _clamp_minutes(value: int) -> int:
  return max(30, min(value, 1440))


def _compute_summary(rows: List[Dict], window_minutes: int) -> Dict:
  if not rows:
    return {
      "window_minutes": window_minutes,
      "sample_count": 0,
      "avg_score": "–",
      "avg_score_numeric": None,
      "score_hint": "No data recorded yet",
      "events_total": "–",
      "events_head": "–",
      "events_body": "–",
      "events_leg": "–",
      "events_total_numeric": None,
      "temp_avg": "–",
      "temp_avg_numeric": None,
      "light_avg": "–",
      "light_avg_numeric": None,
      "sound_avg": "–",
      "sound_avg_numeric": None,
      "notes": ["Connect a device to start capturing data."],
      "times": [],
      "rms_head": [],
      "rms_body": [],
      "rms_leg": [],
      "temps": [],
      "lights": [],
      "sounds": [],
      "scores": [],
      "last_sample_at": None,
    }

  times: List[datetime] = []
  rms_head: List[float] = []
  rms_body: List[float] = []
  rms_leg: List[float] = []
  temps: List[float] = []
  lights: List[int] = []
  sounds: List[float] = []
  scores: List[float] = []
  events_min_head: List[int] = []
  events_min_body: List[int] = []
  events_min_leg: List[int] = []
  total_events_min: List[int] = []

  for payload in rows:
    ts = _parse_timestamp(payload)
    times.append(ts)
    rms_head.append(float(payload.get("RMS_H", 0.0)))
    rms_body.append(float(payload.get("RMS_B", 0.0)))
    rms_leg.append(float(payload.get("RMS_L", 0.0)))
    temps.append(float(payload.get("TempC", 0.0)))
    lights.append(int(payload.get("LightRaw", 0)))
    sounds.append(float(payload.get("SoundRMS", 0.0)))
    scores.append(float(payload.get("SleepScore", 0.0)))
    events_min_head.append(int(payload.get("minute_events_H", 0)))
    events_min_body.append(int(payload.get("minute_events_B", 0)))
    events_min_leg.append(int(payload.get("minute_events_L", 0)))
    total_events_min.append(int(payload.get("total_events_min", 0)))

  sample_count = len(rows)
  avg_score = sum(scores) / sample_count if sample_count else 0.0
  avg_events_total = sum(total_events_min) / sample_count if sample_count else 0.0
  avg_events_head = sum(events_min_head) / sample_count if sample_count else 0.0
  avg_events_body = sum(events_min_body) / sample_count if sample_count else 0.0
  avg_events_leg = sum(events_min_leg) / sample_count if sample_count else 0.0
  avg_temp = sum(temps) / sample_count if sample_count else 0.0
  avg_light = sum(lights) / sample_count if sample_count else 0.0
  avg_sound = sum(sounds) / sample_count if sample_count else 0.0

  notes: List[str] = [_score_hint(avg_score)]
  if avg_events_total >= 10:
    notes.append("High overall activity")
  elif avg_events_total >= 5:
    notes.append("Moderate nightly activity")
  else:
    notes.append("Low activity baseline")

  if avg_temp < 18:
    notes.append("Room trending cool")
  elif avg_temp > 26:
    notes.append("Room trending warm")

  return {
    "window_minutes": window_minutes,
    "sample_count": sample_count,
    "avg_score": f"{avg_score:.1f}",
    "avg_score_numeric": avg_score,
    "score_hint": _score_hint(avg_score),
    "events_total": f"{avg_events_total:.1f}",
    "events_head": f"{avg_events_head:.1f}",
    "events_body": f"{avg_events_body:.1f}",
    "events_leg": f"{avg_events_leg:.1f}",
    "events_total_numeric": avg_events_total,
    "events_head_numeric": avg_events_head,
    "events_body_numeric": avg_events_body,
    "events_leg_numeric": avg_events_leg,
    "temp_avg": f"{avg_temp:.1f}",
    "temp_avg_numeric": avg_temp,
    "light_avg": f"{avg_light:.0f}",
    "light_avg_numeric": avg_light,
    "sound_avg": f"{avg_sound:.1f}",
    "sound_avg_numeric": avg_sound,
    "notes": notes,
    "times": times,
    "rms_head": rms_head,
    "rms_body": rms_body,
    "rms_leg": rms_leg,
    "temps": temps,
    "lights": lights,
    "sounds": sounds,
    "scores": scores,
    "last_sample_at": rows[-1].get("recorded_at"),
  }


@app.get("/reports", response_class=HTMLResponse)
async def reports(request: Request, minutes: int = 180) -> HTMLResponse:
  window_minutes = _clamp_minutes(minutes)
  rows = await asyncio.to_thread(database.get_samples_since, window_minutes)
  metrics = _compute_summary(rows, window_minutes)

  if metrics["sample_count"]:
    fig = make_subplots(
      rows=2,
      cols=1,
      shared_xaxes=True,
      vertical_spacing=0.12,
      subplot_titles=("Regional Movement (RMS)", "Environment (Temp / Light / Sound)"),
    )

    fig.add_trace(go.Scatter(x=metrics["times"], y=metrics["rms_head"], name="Head RMS", line=dict(color="#4338ca", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=metrics["times"], y=metrics["rms_body"], name="Body RMS", line=dict(color="#14b8a6", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=metrics["times"], y=metrics["rms_leg"], name="Leg RMS", line=dict(color="#f97316", width=2)), row=1, col=1)

    fig.add_trace(go.Scatter(x=metrics["times"], y=metrics["temps"], name="Temp °C", line=dict(color="#0ea5e9", width=2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=metrics["times"], y=metrics["lights"], name="Light", line=dict(color="#facc15", width=1.6, dash="dot")), row=2, col=1)
    fig.add_trace(go.Scatter(x=metrics["times"], y=metrics["sounds"], name="Sound RMS", line=dict(color="#22d3ee", width=1.8, dash="dash")), row=2, col=1)

    fig.update_layout(
      margin=dict(l=50, r=20, t=60, b=40),
      legend=dict(orientation="h", y=1.15, x=0),
      plot_bgcolor="#ffffff",
      paper_bgcolor="#ffffff",
      font=dict(family="Inter, sans-serif", size=13),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0")
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0")

    plot_movement = pio.to_html(fig, include_plotlyjs="cdn", full_html=False, config={"displayModeBar": False})

    heatmap = go.Figure(
      data=go.Heatmap(
        z=[metrics["scores"]],
        x=[t.strftime("%H:%M") for t in metrics["times"]],
        y=["Sleep Score"],
        colorscale="Blues",
        zmin=0,
        zmax=100,
        hovertemplate="Time %{x}<br>Score %{z:.1f}<extra></extra>",
      )
    )
    heatmap.update_layout(
      margin=dict(l=40, r=20, t=20, b=40),
      plot_bgcolor="#ffffff",
      paper_bgcolor="#ffffff",
      font=dict(family="Inter, sans-serif", size=13),
    )
    plot_heatmap = pio.to_html(heatmap, include_plotlyjs=False, full_html=False, config={"displayModeBar": False})
  else:
    empty = "<div style='padding:40px; text-align:center; color:#64748b;'>No samples in this window.</div>"
    plot_movement = empty
    plot_heatmap = empty

  context = {
    "request": request,
    **{k: metrics[k] for k in [
      "window_minutes",
      "avg_score",
      "score_hint",
      "events_total",
      "events_head",
      "events_body",
      "events_leg",
      "temp_avg",
      "light_avg",
      "sound_avg",
      "sample_count",
      "notes",
    ]},
    "plot_movement": plot_movement,
    "plot_heatmap": plot_heatmap,
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
  }
  return templates.TemplateResponse("report.html", context)


@app.get("/api/summary")
async def api_summary(minutes: int = 180) -> JSONResponse:
  window_minutes = _clamp_minutes(minutes)
  rows = await asyncio.to_thread(database.get_samples_since, window_minutes)
  metrics = _compute_summary(rows, window_minutes)
  payload = {
    "window_minutes": window_minutes,
    "sample_count": metrics["sample_count"],
    "average_sleep_score": metrics.get("avg_score_numeric"),
    "score_hint": metrics["score_hint"],
    "movement_events_per_min": {
      "total": metrics.get("events_total_numeric"),
      "head": metrics.get("events_head_numeric"),
      "body": metrics.get("events_body_numeric"),
      "leg": metrics.get("events_leg_numeric"),
    },
    "environment": {
      "temp_c": metrics.get("temp_avg_numeric"),
      "light": metrics.get("light_avg_numeric"),
      "sound_rms": metrics.get("sound_avg_numeric"),
    },
    "notes": metrics["notes"],
    "last_sample_at": metrics["last_sample_at"],
  }
  return JSONResponse(payload)


@app.get("/api/system-status")
async def api_system_status() -> JSONResponse:
  stats = await asyncio.to_thread(database.get_system_stats)
  payload = {
    "status": "healthy" if stats.get("database", {}).get("connected") else "degraded",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    **stats,
  }
  return JSONResponse(payload)
