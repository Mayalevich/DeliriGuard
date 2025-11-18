"""
Train Custom Sleep Posture Detection Model
Using Local Dataset (No API Required) - Training_data_3 Version
"""

from ultralytics import YOLO
import os
from pathlib import Path
from collections import Counter

# ===== Configuration =====
# Modify this to your dataset path
DATA_PATH = r"E:\Code\198\198\Training_data_3"

# Training Settings
EPOCHS = 50             # Increased to 50 epochs (now we have validation set)
IMG_SIZE = 1280
BATCH_SIZE = 8          # Reduce to 4 if out of memory
MODEL_SIZE = 'n'        # n, s, m, l, x

def check_dataset():
    """Check if dataset exists"""
    data_yaml = f"{DATA_PATH}/data.yaml"
    
    print("=" * 60)
    print("Checking Dataset...")
    print("=" * 60)
    
    if not os.path.exists(DATA_PATH):
        print(f"❌ Dataset folder not found: {DATA_PATH}")
        print("\nPlease ensure:")
        print("1. ZIP file has been downloaded")
        print("2. Extracted to correct location")
        print("3. Folder name is Training_data_3")
        return False
    
    if not os.path.exists(data_yaml):
        print(f"❌ Configuration file not found: {data_yaml}")
        return False
    
    print(f"✓ Dataset path: {DATA_PATH}")
    print(f"✓ Config file: {data_yaml}")
    
    # Display configuration content
    with open(data_yaml, 'r', encoding='utf-8') as f:
        config_content = f.read()
        print("\nDataset Configuration:")
        print(config_content)
    
    # Check key configurations
    print("\n" + "=" * 60)
    print("Key Checks:")
    print("=" * 60)
    
    # Check validation set configuration
    if 'val: valid/images' in config_content or 'val: val/images' in config_content:
        print("✓ Validation set configured correctly")
    elif 'val: train/images' in config_content:
        print("⚠️  Warning: Validation set same as training set (may cause overfitting)")
    else:
        print("⚠️  Validation set configuration may have issues")
    
    # Check class configuration
    if "names:" in config_content:
        if "['Bad-style', 'Good-style']" in config_content:
            print("✓ Class configuration: ['Bad-style', 'Good-style']")
            print("  ℹ️  If only one class detected after training, try swapping to:")
            print("     ['Good-style', 'Bad-style']")
        elif "['Good-style', 'Bad-style']" in config_content:
            print("✓ Class configuration: ['Good-style', 'Bad-style']")
        print("✓ nc: 2 (two classes)")
    
    return True

def check_class_distribution():
    """Check class distribution"""
    print("\n" + "=" * 60)
    print("Checking Class Distribution...")
    print("=" * 60)
    
    def count_classes(label_folder):
        classes = []
        folder_path = Path(label_folder)
        if not folder_path.exists():
            return Counter()
        
        for txt_file in folder_path.glob("*.txt"):
            with open(txt_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        classes.append(int(parts[0]))
        return Counter(classes)
    
    train_labels = Path(DATA_PATH) / "train" / "labels"
    valid_labels = Path(DATA_PATH) / "valid" / "labels"
    
    train_dist = count_classes(train_labels)
    valid_dist = count_classes(valid_labels)
    
    if train_dist:
        print(f"\nTraining Set:")
        print(f"  Class 0: {train_dist.get(0, 0)} annotations")
        print(f"  Class 1: {train_dist.get(1, 0)} annotations")
        total_train = sum(train_dist.values())
        if train_dist.get(0, 0) > 0 and train_dist.get(1, 0) > 0:
            ratio = max(train_dist.values()) / min(train_dist.values())
            print(f"  Ratio: {ratio:.2f}:1")
    
    if valid_dist:
        print(f"\nValidation Set:")
        print(f"  Class 0: {valid_dist.get(0, 0)} annotations")
        print(f"  Class 1: {valid_dist.get(1, 0)} annotations")
    
    # Judgment
    print("\n" + "=" * 60)
    if len(train_dist) == 2 and len(valid_dist) == 2:
        print("✓ Both datasets contain two classes! Ready to train")
        return True
    else:
        print("❌ Warning: Some dataset is missing classes!")
        if len(train_dist) < 2:
            print("  Training set has only one class")
        if len(valid_dist) < 2:
            print("  Validation set has only one class")
        print("\nThis will cause the model to only recognize one class!")
        return False

def train_model():
    """Train YOLO model"""
    print("\n" + "=" * 60)
    print("Starting Model Training...")
    print("=" * 60)
    print(f"Model: YOLO11{MODEL_SIZE}")
    print(f"Epochs: {EPOCHS}")
    print(f"Image Size: {IMG_SIZE}")
    print(f"Batch Size: {BATCH_SIZE}")
    
    # Load pretrained model
    model = YOLO(f'yolo11{MODEL_SIZE}.pt')
    print(f"✓ Pretrained model loaded successfully")
    
    print("\n💡 Monitor during training:")
    print("  - Terminal output should show metrics for two classes")
    print("  - val/cls_loss should decrease")
    print("  - If only one class shown, class mapping is incorrect")
    print("")
    
    # Training
    results = model.train(
        data=f'{DATA_PATH}/data.yaml',
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        name='hospital_dilirium_model_v3',
        patience=20,            # Early stopping: stop if no improvement for 20 epochs
        save=True,
        save_period=10,         # Save checkpoint every 10 epochs
        plots=True,
        device=0,               # GPU, will auto-switch to CPU if unavailable
        
        # Optimizer settings (new)
        optimizer='AdamW',      # Better optimizer
        lr0=0.001,              # Initial learning rate
        lrf=0.01,               # Final learning rate ratio
        
        # Data augmentation - break background dependency
        augment=True,
        hsv_h=0.015,            # Hue variation
        hsv_s=0.7,              # Saturation variation
        hsv_v=0.4,              # Brightness variation
        degrees=10.0,           # Rotation (increased to 10 degrees)
        translate=0.1,          # Translation
        scale=0.5,              # Scaling
        flipud=0.0,             # No vertical flip
        fliplr=0.5,             # Horizontal flip
        mosaic=1.0,             # Mosaic augmentation (mix different backgrounds)
        mixup=0.1,              # Mixup augmentation
        copy_paste=0.1,         # Copy-paste augmentation (new)
        
        # Show detailed information
        verbose=True,
    )
    
    print("\n" + "=" * 60)
    print("✓ Training Complete!")
    print("=" * 60)
    print(f"Best model: runs/detect/hospital_dilirium_model_v3/weights/best.pt")
    print(f"Training charts: runs/detect/hospital_dilirium_model_v3/")
    
    return results

def validate_model():
    """Validate model - show detailed metrics by class"""
    print("\n" + "=" * 60)
    print("Validating Model Performance...")
    print("=" * 60)
    
    model_path = 'runs/detect/hospital_dilirium_model_v3/weights/best.pt'
    
    if not os.path.exists(model_path):
        print(f"❌ Model not found: {model_path}")
        return None
    
    model = YOLO(model_path)
    metrics = model.val(data=f'{DATA_PATH}/data.yaml')
    
    print("\nOverall Performance:")
    print(f"  mAP50:     {metrics.box.map50:.4f}")
    print(f"  mAP50-95:  {metrics.box.map:.4f}")
    print(f"  Precision: {metrics.box.mp:.4f}")
    print(f"  Recall:    {metrics.box.mr:.4f}")
    
    # Display by class (new)
    print("\n" + "=" * 60)
    print("Performance by Class:")
    print("=" * 60)
    
    if hasattr(metrics.box, 'ap_class_index') and len(metrics.box.ap_class_index) > 0:
        # Class names
        class_names = {0: 'Bad-style', 1: 'Good-style'}
        
        print(f"\nDetected {len(metrics.box.ap_class_index)} classes:")
        
        for i, class_id in enumerate(metrics.box.ap_class_index):
            class_name = class_names.get(int(class_id), f'Class-{class_id}')
            print(f"\n  {class_name}:")
            if i < len(metrics.box.ap50):
                print(f"    AP50:     {metrics.box.ap50[i]:.4f}")
            if i < len(metrics.box.ap):
                print(f"    AP50-95:  {metrics.box.ap[i]:.4f}")
        
        # Judge success/failure
        print("\n" + "=" * 60)
        if len(metrics.box.ap_class_index) == 2:
            print("✅ Success! Both classes can be recognized!")
            
            # Check performance
            if metrics.box.map50 > 0.7:
                print("✅ Model performance is good (mAP50 > 0.7)")
            elif metrics.box.map50 > 0.5:
                print("⚠️  Model performance is average (mAP50 = 0.5-0.7)")
                print("   Consider:")
                print("   - Increase training epochs")
                print("   - Check difficult samples")
            else:
                print("⚠️  Model performance is poor (mAP50 < 0.5)")
                print("   Need:")
                print("   - More training data")
                print("   - Check annotation quality")
                print("   - Longer training time")
        else:
            print("❌ Failed! Only one class detected")
            print("\n🔧 Solution:")
            print("1. Modify data.yaml, swap class order:")
            print("   names: ['Good-style', 'Bad-style']")
            print("2. Retrain the model")
            print("3. Or check if dataset really contains two classes")
    else:
        print("⚠️  Unable to get per-class performance metrics")
    
    return metrics

def check_results():
    """Check training result files"""
    print("\n" + "=" * 60)
    print("Checking Training Result Files...")
    print("=" * 60)
    
    results_dir = Path("runs/detect/hospital_dilirium_model_v3")
    
    if not results_dir.exists():
        print("⚠️  Results folder does not exist")
        return
    
    important_files = {
        'results.png': 'Training curves (loss and metrics)',
        'confusion_matrix.png': 'Confusion matrix (Most Important!)',
        'confusion_matrix_normalized.png': 'Normalized confusion matrix',
        'labels.jpg': 'Label distribution chart',
        'F1_curve.png': 'F1 score curve',
        'PR_curve.png': 'Precision-Recall curve',
        'P_curve.png': 'Precision curve',
        'R_curve.png': 'Recall curve',
    }
    
    print("\nGenerated files:")
    for file, desc in important_files.items():
        file_path = results_dir / file
        if file_path.exists():
            print(f"  ✓ {file:40s} - {desc}")
        else:
            print(f"  ✗ {file:40s} - {desc} (not generated)")
    
    # Highlight confusion matrix
    confusion_matrix = results_dir / "confusion_matrix.png"
    if confusion_matrix.exists():
        print("\n" + "=" * 60)
        print("⭐ Key Check - Confusion Matrix:")
        print("=" * 60)
        print(f"Open file: {confusion_matrix}")
        print("\nShould see 2×2 matrix:")
        print("  ┌──────────────┬──────────┬──────────┐")
        print("  │              │ Pred Bad │ Pred Good│")
        print("  ├──────────────┼──────────┼──────────┤")
        print("  │ True Bad     │   [High] │   [Low]  │")
        print("  │ True Good    │   [Low]  │   [High] │")
        print("  └──────────────┴──────────┴──────────┘")
        print("\n✓ High diagonal numbers = both classes recognized")
        print("✗ One row all low numbers = that class not recognized")

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║   Hospital Dilirium Detection - Model Training          ║
    ║   Dataset: Training_data_3                               ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Step 1: Check dataset
    if not check_dataset():
        print("\nPlease download and extract the dataset first!")
        exit(1)
    
    # Step 2: Check class distribution
    if not check_class_distribution():
        print("\n⚠️  Dataset has issues, but can try to continue training")
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled")
            exit(1)
    
    # Step 3: Train
    print("\nReady to start training...")
    print("Press Enter to continue, Ctrl+C to cancel")
    try:
        input()
    except KeyboardInterrupt:
        print("\nCancelled")
        exit(0)
    
    try:
        results = train_model()
    except Exception as e:
        print(f"\n✗ Training failed: {e}")
        print("\nPossible solutions:")
        print("1. Out of memory: set BATCH_SIZE = 4")
        print("2. No GPU: will auto-use CPU (slower)")
        print("3. Wrong dataset path: check DATA_PATH")
        import traceback
        traceback.print_exc()
        exit(1)
    
    # Step 4: Check result files
    check_results()
    
    # Step 5: Validate
    try:
        validate_model()
    except Exception as e:
        print(f"\n✗ Validation failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Complete
    print("\n" + "=" * 60)
    print("🎉 Training Complete!")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Check confusion matrix (Most important):")
    print("   runs/detect/hospital_dilirium_model_v3/confusion_matrix.png")
    print("\n2. Check training curves:")
    print("   runs/detect/hospital_dilirium_model_v3/results.png")
    print("\n3. If both classes recognized, update detection code:")
    print("   MODEL_PATH = r'runs/detect/hospital_dilirium_model_v3/weights/best.pt'")
    print("\n4. If only one class detected:")
    print("   - Modify data.yaml, swap class order")
    print("   - Rerun this script")
    print("=" * 60)