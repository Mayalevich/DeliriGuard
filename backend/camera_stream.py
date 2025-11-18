"""
Camera stream endpoint for posture detection debugging
"""

import asyncio
import logging
from typing import Optional
import cv2
import numpy as np

logger = logging.getLogger("sleep-backend")

class CameraStream:
    """Stream camera feed for debugging"""
    
    def __init__(self, video_source: str = "0"):
        self.video_source = video_source
        self.cap: Optional[cv2.VideoCapture] = None
        self.running = False
    
    def start(self):
        """Start camera stream"""
        if self.cap is not None:
            return
        
        try:
            if self.video_source.isdigit():
                self.cap = cv2.VideoCapture(int(self.video_source))
            else:
                self.cap = cv2.VideoCapture(self.video_source)
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera: {self.video_source}")
                return False
            
            # Set lower resolution for streaming
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            self.running = True
            logger.info(f"Camera stream started: {self.video_source}")
            return True
        except Exception as e:
            logger.error(f"Error starting camera stream: {e}")
            return False
    
    def read_frame(self):
        """Read a frame from camera"""
        if not self.cap or not self.cap.isOpened():
            return None
        
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        return frame
    
    def stop(self):
        """Stop camera stream"""
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        logger.info("Camera stream stopped")

# Global camera stream instance
camera_stream: Optional[CameraStream] = None

def get_camera_stream(video_source: str = "0") -> CameraStream:
    """Get or create camera stream instance"""
    global camera_stream
    if camera_stream is None:
        camera_stream = CameraStream(video_source)
    return camera_stream

