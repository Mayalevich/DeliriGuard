"""
Sleep Behavior Analysis System - Multi-Class Detection
Good-Style: Green box | Bad-Style: Red box
"""

import cv2
import numpy as np
from ultralytics import YOLO
import time
from datetime import datetime
from collections import Counter, deque
import threading
from queue import Queue

# ===== Configuration =====
IP_WEBCAM_URL = "http://192.168.1.100:8080/video"
CONFIDENCE_THRESHOLD = 0.5
SHOW_STATISTICS = True
SAVE_VIDEO = False

# ===== Performance Settings =====
SKIP_FRAMES = 3              # Process every Nth frame (1=every frame, 3=every 3rd frame)
RESIZE_WIDTH = 640           # Lower resolution for faster processing (original is usually 1280 or 1920)
USE_GPU = True               # Try to use GPU if available
MAX_HISTORY = 1000           # Maximum history records to keep in memory
DRAW_EVERY_N_FRAMES = 2      # Update info panel every N frames

# YOLO Optimization
YOLO_IMGSZ = 416             # Smaller input size for faster inference (default 640)
USE_HALF_PRECISION = False   # FP16 for GPU (requires CUDA)


class VideoStream:
    """Threaded video stream to reduce I/O blocking"""
    
    def __init__(self, src):
        self.stream = cv2.VideoCapture(src)
        self.stopped = False
        self.frame = None
        self.grabbed = False
        
        # Set buffer size to 1 to reduce lag
        self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
    def start(self):
        threading.Thread(target=self.update, args=(), daemon=True).start()
        return self
    
    def update(self):
        while not self.stopped:
            if not self.grabbed:
                self.grabbed, self.frame = self.stream.read()
            else:
                # Discard old frames to reduce lag
                self.stream.grab()
    
    def read(self):
        self.grabbed = False
        return self.frame
    
    def stop(self):
        self.stopped = True
        self.stream.release()
    
    def isOpened(self):
        return self.stream.isOpened()


class OptimizedSleepAnalyzer:
    """High-Performance Sleep Analyzer with custom trained model"""
    
    def __init__(self):
        print("Initializing Custom Sleep Posture Detection Model...")
        
        # Initialize YOLO with your custom trained model
        MODEL_PATH = r'E:\Code\198\198\Training_data_3\runs\detect\hospital_dilirium_model_v3\weights\best.pt'
        
        try:
            self.model = YOLO(MODEL_PATH)
            print(f"✓ Model loaded from: {MODEL_PATH}")
        except Exception as e:
            print(f"✗ Error loading model: {e}")
            print(f"Please verify MODEL_PATH is correct")
            raise
        
        # Try to use GPU
        if USE_GPU:
            try:
                import torch
                if torch.cuda.is_available():
                    print(f"✓ Using GPU: {torch.cuda.get_device_name(0)}")
                    if USE_HALF_PRECISION:
                        self.model.to('cuda').half()
                        print("✓ Half precision (FP16) enabled")
                else:
                    print("ℹ GPU not available, using CPU")
            except ImportError:
                print("ℹ PyTorch not installed, using CPU")
        
        self.start_time = time.time()
        self.person_detections = 0
        self.posture_history = deque(maxlen=MAX_HISTORY)
        
        # Get class names directly from model
        self.class_names = self.model.names  # e.g., {0: 'goodstyle', 1: 'badstyle'}
        print(f"✓ Detected classes: {list(self.class_names.values())}")
        
        # Performance tracking
        self.fps_history = deque(maxlen=30)
        self.last_detection_result = None
        self.frame_counter = 0
        
        # Info panel cache
        self.cached_panel = None
        self.panel_update_counter = 0
        
        print("✓ Model initialized successfully!")
    
    def format_class_name(self, class_name):
        """
        Format class name for display
        'goodstyle' or 'Good-style' -> 'Good-Style'
        'badstyle' or 'Bad-style' -> 'Bad-Style'
        """
        # Convert to lowercase for comparison
        class_lower = class_name.lower().replace('-', '').replace('_', '').replace(' ', '')
        
        if 'good' in class_lower:
            return 'Good-Style'
        elif 'bad' in class_lower:
            return 'Bad-Style'
        else:
            # For any other class, capitalize properly
            return class_name.replace('-', ' ').replace('_', ' ').title().replace(' ', '-')
    
    def draw_info_panel(self, frame):
        """Draw information panel (cached for performance)"""
        h, w = frame.shape[:2]
        
        # Only update panel every N frames
        if self.panel_update_counter % DRAW_EVERY_N_FRAMES == 0:
            panel = np.zeros((180, 320, 3), dtype=np.uint8)
            panel[:] = (40, 40, 40)
            
            # Title
            cv2.putText(panel, "Sleep Monitor", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            # Runtime
            elapsed = int(time.time() - self.start_time)
            time_str = f"Time: {elapsed//3600:02d}:{(elapsed%3600)//60:02d}:{elapsed%60:02d}"
            cv2.putText(panel, time_str, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # FPS
            if self.fps_history:
                avg_fps = sum(self.fps_history) / len(self.fps_history)
                cv2.putText(panel, f"FPS: {avg_fps:.1f}", (10, 85),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Current posture
            if self.posture_history:
                current = self.posture_history[-1]
                formatted_name = self.format_class_name(current)
                cv2.putText(panel, f"Current:", (10, 115),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                
                # Show posture with color
                color = self.get_posture_color(current)
                cv2.putText(panel, formatted_name, (10, 140),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                # Add color indicator
                cv2.rectangle(panel, (10, 150), (30, 165), color, -1)
            
            self.cached_panel = panel
        
        self.panel_update_counter += 1
        
        # Overlay cached panel
        if self.cached_panel is not None:
            frame[10:190, w-330:w-10] = self.cached_panel
        
        return frame
    
    def process_frame(self, frame, do_detection=True):
        """Process single frame with optional detection skip"""
        frame_start = time.time()
        
        # Resize frame for faster processing
        h, w = frame.shape[:2]
        if w > RESIZE_WIDTH:
            scale = RESIZE_WIDTH / w
            new_w = RESIZE_WIDTH
            new_h = int(h * scale)
            frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        else:
            frame_resized = frame
            scale = 1.0
        
        annotated = frame_resized.copy()
        
        # Only run detection every N frames
        if do_detection:
            # YOLO detection with optimization
            results = self.model(
                frame_resized, 
                conf=CONFIDENCE_THRESHOLD, 
                verbose=False,
                imgsz=YOLO_IMGSZ,
                half=USE_HALF_PRECISION
            )[0]
            
            # Cache result for skipped frames
            self.last_detection_result = results
        else:
            # Use cached result
            results = self.last_detection_result
        
        # Draw detection results
        person_detected = False
        
        if results is not None:
            for box in results.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Process all detected classes
                person_detected = True
                
                if do_detection:  # Only count on detection frames
                    self.person_detections += 1
                
                # Get coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Get class name from model
                class_name = self.class_names.get(cls, f'Class-{cls}')
                
                if do_detection:  # Only update history on detection frames
                    self.posture_history.append(class_name)
                
                # Get color for this class (GREEN for Good-Style, RED for Bad-Style)
                color = self.get_posture_color(class_name)
                
                # Draw bounding box with thicker line for better visibility
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
                
                # Format class name for display
                formatted_name = self.format_class_name(class_name)
                
                # Create label with formatted name
                label = f"{formatted_name}: {conf:.2f}"
                
                # Draw label background for better readability
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                label_bg_y1 = max(y1 - label_size[1] - 10, 0)
                label_bg_y2 = y1
                cv2.rectangle(annotated, (x1, label_bg_y1), (x1 + label_size[0] + 10, label_bg_y2), color, -1)
                
                # Draw label text in white for contrast
                cv2.putText(annotated, label, (x1 + 5, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Add warning (only if not detected on a detection frame)
        if do_detection and not person_detected:
            cv2.putText(annotated, "No detection", (10, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Draw info panel
        if SHOW_STATISTICS:
            annotated = self.draw_info_panel(annotated)
        
        # Calculate FPS
        frame_time = time.time() - frame_start
        fps = 1.0 / frame_time if frame_time > 0 else 0
        self.fps_history.append(fps)
        
        return annotated
    
    def get_posture_color(self, class_name):
        """
        Get color for class name
        Good-Style: GREEN (0, 255, 0)
        Bad-Style: RED (0, 0, 255)
        """
        # Convert to lowercase for comparison
        class_lower = class_name.lower().replace('-', '').replace('_', '').replace(' ', '')
        
        if 'good' in class_lower:
            return (0, 255, 0)  # GREEN for Good-Style
        elif 'bad' in class_lower:
            return (0, 0, 255)  # RED for Bad-Style
        else:
            # Default colors for other classes
            colors = {
                'side-sleeping': (255, 255, 0),    # Cyan
                'back-sleeping': (255, 0, 255),    # Magenta
                'stomach-sleeping': (0, 255, 255), # Yellow
            }
            return colors.get(class_name.lower(), (255, 255, 0))  # Default yellow
    
    def generate_summary(self):
        """Generate analysis summary"""
        if not self.posture_history:
            return "No detection data"
        
        posture_counts = Counter(self.posture_history)
        
        total = len(self.posture_history)
        summary = "\n" + "="*50 + "\n"
        summary += "Sleep Analysis Summary\n"
        summary += "="*50 + "\n"
        summary += f"Total detection frames: {total}\n"
        summary += f"Total duration: {int(time.time() - self.start_time)} seconds\n"
        
        if self.fps_history:
            avg_fps = sum(self.fps_history) / len(self.fps_history)
            summary += f"Average FPS: {avg_fps:.1f}\n\n"
        
        summary += "Posture Distribution:\n"
        
        for class_name, count in posture_counts.most_common():
            percentage = (count / total) * 100
            formatted_name = self.format_class_name(class_name)
            summary += f"  {formatted_name:20s}: {count:5d} ({percentage:5.1f}%)\n"
        
        summary += "="*50 + "\n"
        return summary
    
    def run(self):
        """Run optimized analysis system"""
        print("\n" + "="*60)
        print("Sleep Behavior Analysis - MULTI-CLASS VERSION")
        print("="*60)
        print("Color Coding:")
        print("  🟢 Good-Style: GREEN box")
        print("  🔴 Bad-Style:  RED box")
        print(f"\nConnecting to: {IP_WEBCAM_URL}")
        print(f"\nPerformance Settings:")
        print(f"  Skip Frames: {SKIP_FRAMES} (process every {SKIP_FRAMES+1}th frame)")
        print(f"  Resize Width: {RESIZE_WIDTH}px")
        print(f"  YOLO Image Size: {YOLO_IMGSZ}px")
        
        # Use threaded video stream
        cap = VideoStream(IP_WEBCAM_URL).start()
        time.sleep(1.0)  # Allow camera to warm up
        
        if not cap.isOpened():
            print("✗ Unable to connect to camera")
            print("\nPlease check:")
            print("1. IP address is correct")
            print("2. IP Webcam app is running")
            print("3. Phone and computer are on the same network")
            return
        
        print("✓ Connected successfully!")
        print("\nControl Keys:")
        print("  q - Quit")
        print("  s - Screenshot")
        print("  p - Pause/Resume")
        print("  + - Increase skip frames (faster, less accurate)")
        print("  - - Decrease skip frames (slower, more accurate)")
        print("\nStarting analysis...\n")
        
        video_writer = None
        paused = False
        self.frame_counter = 0
        skip_frames = SKIP_FRAMES
        
        try:
            while True:
                if not paused:
                    frame = cap.read()
                    
                    if frame is None:
                        time.sleep(0.01)
                        continue
                    
                    self.frame_counter += 1
                    
                    # Decide whether to run detection
                    do_detection = (self.frame_counter % (skip_frames + 1) == 0)
                    
                    # Process frame
                    processed = self.process_frame(frame, do_detection)
                    
                    # Add frame info
                    info_text = f"Frame: {self.frame_counter} | Skip: {skip_frames}"
                    cv2.putText(processed, info_text, (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    if video_writer:
                        video_writer.write(processed)
                else:
                    if frame is None:
                        continue
                    processed = frame.copy()
                    cv2.putText(processed, "PAUSED - Press 'p' to continue", 
                               (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                
                cv2.imshow('Sleep Monitor - Multi-Class (Press q to quit)', processed)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(filename, processed)
                    print(f"✓ Screenshot saved: {filename}")
                elif key == ord('p'):
                    paused = not paused
                    print(f"{'Paused' if paused else 'Resumed'} analysis")
                elif key == ord('+') or key == ord('='):
                    skip_frames = min(skip_frames + 1, 10)
                    print(f"Skip frames: {skip_frames} (faster)")
                elif key == ord('-') or key == ord('_'):
                    skip_frames = max(skip_frames - 1, 0)
                    print(f"Skip frames: {skip_frames} (slower)")
        
        except KeyboardInterrupt:
            print("\nProgram interrupted")
        
        finally:
            print("\nCleaning up resources...")
            if video_writer:
                video_writer.release()
                print("✓ Video saved: output.mp4")
            
            cap.stop()
            cv2.destroyAllWindows()
            
            # Print summary
            print(self.generate_summary())
            
            # Save log
            with open('analysis_log.txt', 'w', encoding='utf-8') as f:
                f.write(self.generate_summary())
            print("✓ Analysis log saved: analysis_log.txt")


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║   Sleep Behavior Analysis - MULTI-CLASS DETECTION        ║
    ║                                                          ║
    ║  Color Coding:                                           ║
    ║   Good-Style  → GREEN box                                ║
    ║   Bad-Style   → RED box                                  ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Get user input
    print("\nEnter your IP Webcam address (or press Enter for default):")
    user_input = input(f"Default: {IP_WEBCAM_URL}\n> ").strip()
    if user_input:
        IP_WEBCAM_URL = user_input
    
    # Performance tips
    print("\n💡 Performance Tips:")
    print("  • If too slow: Press '+' to skip more frames")
    print("  • If too fast but jerky: Press '-' to skip fewer frames")
    print("")
    
    # Run analyzer
    analyzer = OptimizedSleepAnalyzer()
    analyzer.run()