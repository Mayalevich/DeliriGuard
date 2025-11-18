"""
Posture Detection Service for Sleep Monitoring
Integrates YOLO-based posture detection with the sleep monitoring backend
"""

import asyncio
import logging
import os
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    """Posture detection using YOLO model"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path or self._find_model_path()
        self.class_names = {}
        self.initialized = False
        
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
            # Patch torch.load to allow loading older model files
            # PyTorch 2.6+ requires weights_only=False for older model files
            import torch
            original_load = torch.load
            
            def patched_load(*args, **kwargs):
                # Set weights_only=False if not explicitly set
                if 'weights_only' not in kwargs:
                    kwargs['weights_only'] = False
                return original_load(*args, **kwargs)
            
            # Temporarily patch torch.load
            torch.load = patched_load
            try:
                self.model = YOLO(self.model_path)
            finally:
                # Restore original torch.load
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
        # Check project root
        project_root = Path(__file__).resolve().parent.parent
        model_path = project_root / "best_model.pt"
        if model_path.exists():
            return str(model_path)
        
        # Check backend directory
        backend_path = Path(__file__).resolve().parent / "best_model.pt"
        if backend_path.exists():
            return str(backend_path)
        
        return None
    
    def detect(self, frame, confidence: float = 0.5) -> List[Dict]:
        """
        Detect postures in a frame
        
        Args:
            frame: numpy array (OpenCV frame)
            confidence: confidence threshold
        
        Returns:
            List of detections with format:
            [{
                'class_name': str,
                'confidence': float,
                'bbox': [x1, y1, x2, y2]
            }]
        """
        if not self.initialized or self.model is None:
            return []
        
        if not CV2_AVAILABLE or frame is None:
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
            return (0, 255, 0)  # GREEN (BGR)
        elif 'bad' in class_lower:
            return (0, 0, 255)  # RED (BGR)
        else:
            return (255, 255, 0)  # Yellow (BGR)


class PostureDetectionService:
    """Service for continuous posture detection from video stream"""
    
    def __init__(
        self,
        video_source: Optional[str] = None,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        process_interval: float = 1.0,  # Process every N seconds
    ):
        self.video_source = video_source or os.environ.get("POSTURE_VIDEO_SOURCE", "0")  # 0 = default camera
        self.confidence_threshold = confidence_threshold
        self.process_interval = process_interval
        
        self.detector = PostureDetector(model_path)
        self.cap: Optional[cv2.VideoCapture] = None
        self.running = False
        self._task: Optional[asyncio.Task] = None
        
        # History tracking
        self.posture_history: deque = deque(maxlen=1000)
        self.last_detection_time = 0.0
        self.last_detection: Optional[Dict] = None
        
        # Statistics
        self.total_detections = 0
        self.start_time: Optional[float] = None
    
    async def start(self) -> None:
        """Start the posture detection service"""
        if not CV2_AVAILABLE:
            logger.warning("OpenCV not available. Posture detection service will not start.")
            return
        
        # Allow service to start even without model - camera will work, just no detection
        if not self.detector.initialized:
            logger.warning("Posture detector not initialized. Camera will start but posture detection will be disabled.")
            logger.warning("To enable detection, ensure best_model.pt is available in project root or backend directory.")
        
        if self._task and not self._task.done():
            return
        
        self.running = True
        self.start_time = time.time()
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run())
        logger.info(f"Posture detection service starting (source: {self.video_source}, model: {'loaded' if self.detector.initialized else 'not available'})")
    
    async def stop(self) -> None:
        """Stop the posture detection service"""
        self.running = False
        if self._task:
            await self._task
        if self.cap:
            self.cap.release()
            self.cap = None
        logger.info("Posture detection service stopped")
    
    async def _run(self) -> None:
        """Main detection loop"""
        try:
            # Open video source
            if not CV2_AVAILABLE:
                logger.error("OpenCV not available. Cannot open video source.")
                self.running = False
                return
            
            if self.video_source.isdigit():
                self.cap = cv2.VideoCapture(int(self.video_source))
            else:
                self.cap = cv2.VideoCapture(self.video_source)
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open video source: {self.video_source}")
                self.running = False
                return
            
            logger.info(f"Video source opened: {self.video_source}")
            
            last_process_time = time.time()
            
            while self.running:
                ret, frame = await asyncio.to_thread(lambda: self.cap.read())
                
                if not ret:
                    logger.warning("Failed to read frame from video source")
                    await asyncio.sleep(0.1)
                    continue
                
                # Process frame at specified interval
                current_time = time.time()
                if current_time - last_process_time >= self.process_interval:
                    detections = await asyncio.to_thread(
                        self.detector.detect,
                        frame,
                        self.confidence_threshold
                    )
                    
                    if detections:
                        # Use the highest confidence detection
                        best_detection = max(detections, key=lambda d: d['confidence'])
                        formatted_posture = self.detector.format_class_name(best_detection['class_name'])
                        self.last_detection = {
                            'posture': formatted_posture,
                            'class_name': best_detection['class_name'],
                            'confidence': best_detection['confidence'],
                            'detected_at': datetime.now(timezone.utc).isoformat(),
                        }
                        self.posture_history.append(best_detection['class_name'])
                        self.total_detections += 1
                        self.last_detection_time = current_time
                        
                        # Save to database (import here to avoid circular imports)
                        try:
                            from . import database
                            database.save_posture_detection(
                                posture=formatted_posture,
                                class_name=best_detection['class_name'],
                                confidence=best_detection['confidence'],
                            )
                        except Exception as e:
                            logger.warning(f"Failed to save posture detection to database: {e}")
                    
                    last_process_time = current_time
                
                # Small delay to prevent CPU spinning
                await asyncio.sleep(0.033)  # ~30 FPS max
                
        except Exception as e:
            logger.error(f"Error in posture detection loop: {e}", exc_info=True)
            self.running = False
        finally:
            if self.cap:
                self.cap.release()
                self.cap = None
    
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

