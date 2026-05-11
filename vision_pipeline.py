from inference_sdk import InferenceHTTPClient
import easyocr
import cv2
import csv
import re
from datetime import datetime

# ── Setup ──────────────────────────────────────────
client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key="N5PvCyk9suYtZhpjktnz"
)
reader = easyocr.Reader(['en'])

# ── Indian Plate Regex ─────────────────────────────
def extract_indian_plate(text):
    text = text.upper().replace(" ", "")
    patterns = [
        r'[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}',  # MH12AB1234
        r'[A-Z]{2}[0-9]{2}[A-Z]{1}[0-9]{4}',   # DL8CA1234
        r'[0-9]{2}BH[0-9]{4}[A-Z]{2}',          # 22BH1234AB
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group()
    return text

# ── Preprocess Plate ───────────────────────────────
def preprocess_plate(plate_img):
    plate_img = cv2.resize(plate_img, None, fx=2, fy=2,
                           interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh

# ── Process Single Frame ───────────────────────────
def process_frame(frame, frame_count):
    # Save frame temporarily
    temp_path = "temp_frame.jpg"
    cv2.imwrite(temp_path, frame)

    try:
        # Detect via Roboflow API
        result = client.run_workflow(
            workspace_name="pratyushs-workspace-3seju",
            workflow_id="general-segmentation-api-2",
            images={"image": temp_path},
            parameters={"classes": "License_Plate"},
            use_cache=True
        )
        predictions = result[0]["predictions"]["predictions"]
    except:
        return frame

    for pred in predictions:
        x = int(pred["x"])
        y = int(pred["y"])
        w = int(pred["width"])
        h = int(pred["height"])

        x1 = max(0, x - w//2)
        y1 = max(0, y - h//2)
        x2 = min(frame.shape[1], x + w//2)
        y2 = min(frame.shape[0], y + h//2)

        plate_crop = frame[y1:y2, x1:x2]
        if plate_crop.size == 0:
            continue

        # OCR
        processed = preprocess_plate(plate_crop)
        ocr_result = reader.readtext(
            processed,
            allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        )
        raw_text = " ".join([r[1] for r in ocr_result])
        plate_number = extract_indian_plate(raw_text)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Log to CSV
        with open("gate_log.csv", "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, plate_number, f"frame_{frame_count}"])

        print(f"✅ Frame {frame_count} | Plate: {plate_number} | {timestamp}")

        # Draw on frame
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, plate_number, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    return frame

# ── Main Video Loop ────────────────────────────────
def process_video(video_path):
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("❌ Could not open video")
        return

    # Video writer to save output
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(
        "result_video.mp4",
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps, (width, height)
    )

    frame_count = 0
    PROCESS_EVERY = 10  # process every 10th frame to save API calls

    print("🎥 Processing video... Press Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("✅ Video processing complete!")
            break

        frame_count += 1

        # Only process every Nth frame
        if frame_count % PROCESS_EVERY == 0:
            frame = process_frame(frame, frame_count)

        # Show live
        cv2.imshow("ANPR - Society Gate", frame)
        out.write(frame)

        # Press Q to quit early
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print("💾 Saved result_video.mp4 and gate_log.csv")

# ── Run ───────────────────────────────────────────
if __name__ == "__main__":
    import os
    
    # Try using the video file if it exists, otherwise fallback to the webcam
    if os.path.exists("gate_video.mp4"):
        video_source = "gate_video.mp4"
        print("📹 Using 'gate_video.mp4' for testing...")
    else:
        video_source = 0  # 0 usually corresponds to the default webcam
        print("⚠️ 'gate_video.mp4' not found. Falling back to Live Webcam (0) for testing...")
        print("💡 Hint: You can hold up your phone displaying a license plate to the camera!")
        
    process_video(video_source)
