"""
Posture Detection Service for Sleep Monitoring
Integrates YOLO-based posture detection with the sleep monitoring backend.
Optimized with:
- Decoupled asynchronous throttled inference worker (1–2 Hz).
- Thread-safe detection caching for zero-latency streaming overlays.
- Unified CameraManager integration (no duplicate camera handles).
"""

import asyncio
import logging
import os
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .camera_stream import get_camera_manager

logger = logging.getLogger("sleep-backend")

# Try to import OpenCV, but make it optional
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None
    np = None
    logger.warning("opencv-python not available. Posture detection will be disabled.")

# Try to import YOLO, but make it optional
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("ultralytics not available. Posture detection will be disabled.")


class PostureDetector:
    """Posture detection using YOLO model with caching support"""

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path or self._find_model_path()
        self.class_names = {}
        self.initialized = False

        # Thread-safe detection result cache for fast stream overlay
        self._cache_lock = threading.Lock()
        self._cached_detections: List[Dict] = []
        self._cached_posture: Optional[str] = None
        self._cached_confidence: float = 0.0
        self._cached_timestamp: float = 0.0

        if not CV2_AVAILABLE:
            logger.warning("OpenCV not available. Posture detection disabled.")
            return

        if not YOLO_AVAILABLE:
            logger.warning("YOLO not available. Posture detection disabled.")
            return

        if not self.model_path or not Path(self.model_path).exists():
            logger.warning(f"Model file not found at {self.model_path}. Posture detection disabled.")
            return

        try:
            # Patch torch.load to allow loading older model files on PyTorch 2.6+
            import torch
            original_load = torch.load

            # Limit thread count so PyTorch doesn't monopolize all CPU cores
            try:
                torch.set_num_threads(min(4, os.cpu_count() or 4))
            except Exception:
                pass

            def patched_load(*args, **kwargs):
                if 'weights_only' not in kwargs:
                    kwargs['weights_only'] = False
                return original_load(*args, **kwargs)

            torch.load = patched_load
            try:
                self.model = YOLO(self.model_path)
            finally:
                torch.load = original_load

            self.class_names = self.model.names
            self.initialized = True
            logger.info(f"✓ Posture detection model loaded: {list(self.class_names.values())}")
        except Exception as e:
            logger.warning(f"Failed to load posture detection model: {e}")
            logger.warning("Posture detection will be disabled. Service will continue without it.")
            self.initialized = False

    def _find_model_path(self) -> Optional[str]:
        """Find the model file in the project directory"""
        project_root = Path(__file__).resolve().parent.parent
        model_path = project_root / "best_model.pt"
        if model_path.exists():
            return str(model_path)

        backend_path = Path(__file__).resolve().parent / "best_model.pt"
        if backend_path.exists():
            return str(backend_path)

        return None

    def detect(self, frame, confidence: float = 0.5) -> List[Dict]:
        """
        Detect postures in a frame
        Returns:
            List of detections: [{'class_name': str, 'confidence': float, 'bbox': [x1, y1, x2, y2]}]
        """
        if not self.initialized or self.model is None or not CV2_AVAILABLE or frame is None:
            return []

        try:
            results = self.model(frame, conf=confidence, verbose=False)[0]
            detections = []

            for box in results.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                class_name = self.class_names.get(cls, f'Class-{cls}')

                detections.append({
                    'class_name': class_name,
                    'confidence': conf,
                    'bbox': [x1, y1, x2, y2]
                })

            return detections
        except Exception as e:
            logger.error(f"Error during posture detection: {e}")
            return []

    def update_cached_detections(self, detections: List[Dict], posture: Optional[str], confidence: float):
        """Update detection cache atomically"""
        with self._cache_lock:
            self._cached_detections = detections
            self._cached_posture = posture
            self._cached_confidence = confidence
            self._cached_timestamp = time.time()

    def get_cached_detections(self) -> Tuple[List[Dict], Optional[str], float, float]:
        """Retrieve latest cached detection instantaneously (< 0.1ms)"""
        with self._cache_lock:
            return list(self._cached_detections), self._cached_posture, self._cached_confidence, self._cached_timestamp

    def format_class_name(self, class_name: str) -> str:
        """Format class name for display"""
        class_lower = class_name.lower().replace('-', '').replace('_', '').replace(' ', '')
        if 'good' in class_lower:
            return 'Good-Style'
        elif 'bad' in class_lower:
            return 'Bad-Style'
        else:
            return class_name.replace('-', ' ').replace('_', ' ').title().replace(' ', '-')

    def get_posture_color(self, class_name: str) -> Tuple[int, int, int]:
        """Get color for posture class (BGR format for OpenCV)"""
        class_lower = class_name.lower().replace('-', '').replace('_', '').replace(' ', '')
        if 'good' in class_lower:
            return (0, 255, 0)  # GREEN
        elif 'bad' in class_lower:
            return (0, 0, 255)  # RED
        else:
            return (255, 255, 0)  # Yellow


class PostureDetectionService:
    """Service for continuous, throttled posture detection (1–2 Hz)"""

    def __init__(
        self,
        video_source: Optional[str] = None,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        process_interval: float = 0.67,  # Process every ~0.67s (~1.5 Hz, throttled to 1-2 Hz)
    ):
        self.video_source = video_source or os.environ.get("POSTURE_VIDEO_SOURCE", "0")
        self.confidence_threshold = confidence_threshold
        self.process_interval = float(os.environ.get("POSTURE_INTERVAL", str(process_interval)))

        self.detector = PostureDetector(model_path)
        self.camera_mgr = get_camera_manager(self.video_source)
        self.running = False
        self._task: Optional[asyncio.Task] = None

        # History tracking
        self.posture_history: deque = deque(maxlen=1000)
        self.last_detection_time = 0.0
        self.last_detection: Optional[Dict] = None

        # Statistics
        self.total_detections = 0
        self.start_time: Optional[float] = None

    @property
    def cap(self):
        """Backward compatibility for cap status inspection"""
        return self.camera_mgr.cap

    async def start(self) -> None:
        """Start the posture detection service"""
        if not CV2_AVAILABLE:
            logger.warning("OpenCV not available. Posture detection service will not start.")
            return

        if not self.detector.initialized:
            logger.warning("Posture detector not initialized. Service will continue without it.")

        if self._task and not self._task.done():
            return

        # Ensure CameraManager is running
        self.camera_mgr.start()

        self.running = True
        self.start_time = time.time()
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run())
        logger.info(f"Posture detection service started (interval: {self.process_interval}s, source: {self.video_source})")

    async def stop(self) -> None:
        """Stop the posture detection service"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.camera_mgr.stop()
        logger.info("Posture detection service stopped")

    async def _run(self) -> None:
        """Decoupled throttled detection loop (runs at 1–2 Hz)"""
        try:
            while self.running:
                t0 = time.perf_counter()

                # Read the latest frame without any buffer lag
                frame, capture_time, frame_id = self.camera_mgr.read_latest_frame(copy=True)

                if frame is not None and self.detector.initialized:
                    # Run inference in separate thread
                    detections = await asyncio.to_thread(
                        self.detector.detect,
                        frame,
                        self.confidence_threshold
                    )

                    current_time = time.time()

                    if detections:
                        best_detection = max(detections, key=lambda d: d['confidence'])
                        formatted_posture = self.detector.format_class_name(best_detection['class_name'])
                        confidence = best_detection['confidence']

                        self.last_detection = {
                            'posture': formatted_posture,
                            'class_name': best_detection['class_name'],
                            'confidence': confidence,
                            'detected_at': datetime.now(timezone.utc).isoformat(),
                        }
                        self.posture_history.append(best_detection['class_name'])
                        self.total_detections += 1
                        self.last_detection_time = current_time

                        # Update cache for real-time MJPEG overlay
                        self.detector.update_cached_detections(detections, formatted_posture, confidence)

                        # Save to database
                        try:
                            from . import database
                            database.save_posture_detection(
                                posture=formatted_posture,
                                class_name=best_detection['class_name'],
                                confidence=confidence,
                            )
                        except Exception as e:
                            logger.warning(f"Failed to save posture detection to database: {e}")
                    else:
                        # Update cache with empty detection
                        self.detector.update_cached_detections([], None, 0.0)

                # Throttle loop to target interval (1–2 Hz)
                elapsed = time.perf_counter() - t0
                sleep_time = max(0.05, self.process_interval - elapsed)
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in posture detection loop: {e}", exc_info=True)
            self.running = False

    def get_current_posture(self) -> Optional[Dict]:
        """Get the most recent posture detection"""
        return self.last_detection

    def get_posture_statistics(self) -> Dict:
        """Get posture detection statistics"""
        if not self.posture_history:
            return {
                'total_detections': 0,
                'posture_distribution': {},
                'runtime_seconds': 0,
            }

        posture_counts = Counter(self.posture_history)
        total = len(self.posture_history)

        distribution = {}
        for class_name, count in posture_counts.items():
            formatted_name = self.detector.format_class_name(class_name)
            distribution[formatted_name] = {
                'count': count,
                'percentage': (count / total) * 100,
                'raw_class': class_name,
            }

        runtime = time.time() - self.start_time if self.start_time else 0

        return {
            'total_detections': self.total_detections,
            'posture_distribution': distribution,
            'runtime_seconds': runtime,
            'last_detection_at': self.last_detection['detected_at'] if self.last_detection else None,
        }

    def get_recent_postures(self, limit: int = 100) -> List[Dict]:
        """Get recent posture detections from history"""
        if not self.posture_history:
            return []

        recent = list(self.posture_history)[-limit:]
        return [
            {
                'posture': self.detector.format_class_name(name),
                'class_name': name,
            }
            for name in recent
        ]
