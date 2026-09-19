"""
High-Performance, Zero-Lag Camera Manager for DeliriGuard Posture Detection and Streaming

Features:
- Dedicated background capture thread to drain driver buffers and eliminate display lag.
- Lock-free / low-contention atomic latest-frame slots with timestamps and frame IDs.
- On-demand viewer presence tracking (avoids unnecessary rendering when no one is watching).
- Unified camera singleton avoiding duplicate handle conflicts on Windows/macOS/Linux.
"""

import logging
import threading
import time
from typing import Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("sleep-backend")


class CameraManager:
    """
    Unified Camera Manager with zero-lag capture thread.
    Drains the camera hardware buffer at native FPS (~30 FPS) so consumers
    always receive the most recent frame captured within the last ~33ms.
    """

    def __init__(self, video_source: str = "0", width: int = 640, height: int = 480):
        self.video_source = video_source
        self.width = width
        self.height = height

        self.cap: Optional[cv2.VideoCapture] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._new_frame_event = threading.Event()

        # Latest frame storage
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_capture_time: float = 0.0
        self.frame_id: int = 0

        # Stats
        self.capture_fps: float = 0.0
        self.dropped_frames: int = 0

        # Viewer presence tracking
        self.active_viewers: int = 0
        self._viewers_lock = threading.Lock()

    def start(self) -> bool:
        """Start the camera and background capture thread"""
        with self._lock:
            if self.running and self._thread and self._thread.is_alive():
                return True

            try:
                if isinstance(self.video_source, str) and self.video_source.isdigit():
                    self.cap = cv2.VideoCapture(int(self.video_source))
                else:
                    self.cap = cv2.VideoCapture(self.video_source)

                if not self.cap.isOpened():
                    logger.error(f"Failed to open video source: {self.video_source}")
                    return False

                # Configure resolution
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

                self.running = True
                self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="CameraCaptureThread")
                self._thread.start()
                logger.info(f"✓ Zero-lag camera capture started on {self.video_source} ({self.width}x{self.height})")
                return True
            except Exception as e:
                logger.error(f"Error opening camera {self.video_source}: {e}")
                self.running = False
                return False

    def _capture_loop(self):
        """Dedicated high-priority loop draining camera hardware buffers"""
        frame_count = 0
        fps_timer = time.perf_counter()

        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            capture_time = time.perf_counter()

            if not ret or frame is None:
                time.sleep(0.01)
                continue

            with self._lock:
                self.latest_frame = frame
                self.latest_capture_time = capture_time
                self.frame_id += 1
                self._new_frame_event.set()

            frame_count += 1
            now = time.perf_counter()
            if now - fps_timer >= 1.0:
                self.capture_fps = frame_count / (now - fps_timer)
                frame_count = 0
                fps_timer = now

        logger.info("Camera capture loop terminated")

    def read_latest_frame(self, copy: bool = False) -> Tuple[Optional[np.ndarray], float, int]:
        """
        Read the latest frame without any buffer backlog.
        Returns:
            (frame, capture_timestamp, frame_id)
        """
        if not self.running:
            self.start()

        with self._lock:
            if self.latest_frame is None:
                return None, 0.0, 0
            frame = self.latest_frame.copy() if copy else self.latest_frame
            return frame, self.latest_capture_time, self.frame_id

    def read_frame(self) -> Optional[np.ndarray]:
        """Backward compatibility for legacy CameraStream.read_frame()"""
        frame, _, _ = self.read_latest_frame(copy=False)
        return frame

    def register_viewer(self) -> int:
        """Register an active MJPEG streaming client"""
        with self._viewers_lock:
            self.active_viewers += 1
            count = self.active_viewers
        logger.info(f"Viewer connected. Active stream viewers: {count}")
        if not self.running:
            self.start()
        return count

    def unregister_viewer(self) -> int:
        """Unregister an MJPEG streaming client"""
        with self._viewers_lock:
            self.active_viewers = max(0, self.active_viewers - 1)
            count = self.active_viewers
        logger.info(f"Viewer disconnected. Active stream viewers: {count}")
        return count

    def has_viewers(self) -> bool:
        """Check if any streaming viewers are currently active"""
        with self._viewers_lock:
            return self.active_viewers > 0

    def stop(self):
        """Stop capture thread and release camera resource"""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        with self._lock:
            if self.cap:
                self.cap.release()
                self.cap = None
            self.latest_frame = None
        logger.info("CameraManager stopped and camera released")


# Global instances registry
_camera_managers: dict = {}
_lock = threading.Lock()


def get_camera_manager(video_source: str = "0") -> CameraManager:
    """Get or create singleton camera manager instance for the video source"""
    global _camera_managers
    with _lock:
        if video_source not in _camera_managers:
            _camera_managers[video_source] = CameraManager(video_source)
        return _camera_managers[video_source]


# Backward compatibility alias
def get_camera_stream(video_source: str = "0") -> CameraManager:
    """Alias for backward compatibility with existing server.py imports"""
    return get_camera_manager(video_source)


class CameraStream:
    """Wrapper class preserving legacy CameraStream interface"""
    def __init__(self, video_source: str = "0"):
        self._manager = get_camera_manager(video_source)

    @property
    def running(self):
        return self._manager.running

    def start(self):
        return self._manager.start()

    def stop(self):
        return self._manager.stop()

    def read_frame(self):
        return self._manager.read_frame()
