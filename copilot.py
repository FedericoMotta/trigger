from business_discovery import get_ig_id_from_username_business_discovery
from downloads import download_media_from_list
import os
import re
import whisper
from PIL import Image
import pytesseract
from collections import defaultdict
from google import genai
import time
import json
from collections import defaultdict
from google.genai.errors import ServerError
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_outliers(user_token, ig_id, username):
    target_ig_id, media_list = get_ig_id_from_username_business_discovery(username, ig_id, user_token, n=100)
    
    average_likes = sum(item['like_count'] for item in media_list) / len(media_list)
    outliers = [item for item in media_list if item['like_count'] > 2 * average_likes]

    print(f"Found {len(outliers)} outlier posts with more than double the average likes ({average_likes:.2f}):")
    download_media_from_list(outliers, n=len(outliers), folder="outlier_media/"+username, user_token=user_token)
    # transcribe_media()
    analyze_all_media(media_dir="outlier_media/"+username, output_path="outlier_media/"+username+"/outlier_media_results.json")


def transcribe_media(media_dir="outlier_media", model_size="base"):
    """
    Transcribes audio/video files and extracts text from image carousels.
    - Audio/video handled by Whisper
    - Images handled by pytesseract (OCR)
    - Carousels grouped by filename prefix (e.g., 12345_1.jpg, 12345_2.jpg)
    """
    print(f"🚀 Starting transcription in: {media_dir}")
    model = whisper.load_model(model_size)

    audio_video_exts = {".mp3", ".mp4", ".wav", ".m4a", ".mov", ".flac"}
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

    def get_carousel_prefix(filename):
        match = re.match(r"^(.+?)_\d+\.[^.]+$", filename)
        return match.group(1) if match else None

    carousel_groups = defaultdict(list)

    # --- Step 1: Categorize files ---
    for filename in os.listdir(media_dir):
        if filename.startswith("."):
            continue  # skip hidden files

        file_path = os.path.join(media_dir, filename)
        if not os.path.isfile(file_path):
            continue

        ext = os.path.splitext(filename)[1].lower()

        # group images for carousels
        if ext in image_exts:
            prefix = get_carousel_prefix(filename)
            if prefix:
                carousel_groups[prefix].append(file_path)
            else:
                carousel_groups[filename] = [file_path]
        elif ext in audio_video_exts:
            carousel_groups[filename] = [file_path]

    # --- Step 2: Process each group ---
    for prefix, files in carousel_groups.items():
        # Check type
        ext = os.path.splitext(files[0])[1].lower()
        is_image_group = ext in image_exts
        is_video_group = ext in audio_video_exts

        if is_image_group:
            if len(files) > 1:
                print(f"🖼️ Processing image carousel: {prefix} ({len(files)} images)")
            else:
                print(f"🖼️ Processing image: {os.path.basename(files[0])}")

            combined_text = ""
            for img_path in sorted(files):
                try:
                    img = Image.open(img_path)
                    text = pytesseract.image_to_string(img, lang="eng")
                    combined_text += f"\n--- {os.path.basename(img_path)} ---\n{text.strip()}\n"
                except Exception as e:
                    print(f"   ❌ Error processing {img_path}: {e}")

            if combined_text.strip():
                txt_path = os.path.join(media_dir, f"{prefix}_images.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(combined_text)
                print(f"✅ Saved OCR text: {txt_path}\n")

        elif is_video_group:
            file_path = files[0]
            filename = os.path.basename(file_path)
            print(f"🎧 Transcribing audio/video: {filename}")
            try:
                result = model.transcribe(file_path)
                transcript = result["text"]

                txt_path = os.path.splitext(file_path)[0] + ".txt"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(transcript)

                print(f"✅ Saved transcript: {txt_path}\n")
            except Exception as e:
                print(f"❌ Error transcribing {filename}: {e}")

    print("🏁 All media processed successfully.")


def merge_images_to_pdf(image_paths, output_path):
    """Merge multiple images into a single multi-page PDF."""
    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    imgs[0].save(output_path, save_all=True, append_images=imgs[1:])
    return output_path


def analyze_all_media(media_dir="outlier_media/", output_path="outlier_media_results.json", max_workers=5):
    client = genai.Client()

    def get_carousel_prefix(filename):
        match = re.match(r"^(.+?)_\d+\.[^.]+$", filename)
        return match.group(1) if match else None

    image_exts = {".jpg", ".jpeg", ".png"}
    audio_video_exts = {".mp4", ".mov"}
    carousel_groups = defaultdict(list)

    # --- Group media ---
    for filename in os.listdir(media_dir):
        if filename.startswith("."):
            continue
        path = os.path.join(media_dir, filename)
        if not os.path.isfile(path):
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext in image_exts:
            prefix = get_carousel_prefix(filename)
            if prefix:
                carousel_groups[prefix].append(path)
            else:
                carousel_groups[filename] = [path]
        elif ext in audio_video_exts:
            carousel_groups[filename] = [path]

    print(f"📦 Found {len(carousel_groups)} media groups in total.")

    # --- Merge carousels into PDFs ---
    prepared_files = []
    for group_name, files in carousel_groups.items():
        if len(files) > 1 and all(os.path.splitext(f)[1].lower() in image_exts for f in files):
            pdf_path = os.path.join(media_dir, f"{group_name}.pdf")
            merge_images_to_pdf(files, pdf_path)
            prepared_files.append((group_name, pdf_path))
            print(f"📄 Merged carousel '{group_name}' into {os.path.basename(pdf_path)}")
        else:
            prepared_files.append((group_name, files[0]))

    print(f"📁 Ready to upload {len(prepared_files)} files (after merging carousels).")

    # --- Upload all files in parallel ---
    def upload_file(group_name, path):
        try:
            media_file = client.files.upload(file=path)
            return group_name, path, media_file
        except Exception as e:
            print(f"❌ Upload failed for {path}: {e}")
            return group_name, path, None

    print(f"🚀 Uploading in parallel (max {max_workers} workers)...")
    uploaded_files = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(upload_file, g, p): (g, p) for g, p in prepared_files}
        for fut in as_completed(futures):
            group_name, path, media_file = fut.result()
            if media_file:
                uploaded_files.append((group_name, media_file))
                print(f"✅ Uploaded {os.path.basename(path)}")
            else:
                print(f"⚠️ Skipped {os.path.basename(path)} due to error.")

    # --- Wait for all to become ACTIVE (parallel) ---
    def wait_until_active(group_name, media_file, retries=20, delay=2):
        for _ in range(retries):
            file_info = client.files.get(name=media_file.name)
            if file_info.state.name == "ACTIVE":
                return group_name, media_file
            elif file_info.state.name == "FAILED":
                raise RuntimeError(f"{media_file.name} failed to process.")
            time.sleep(delay)
        raise TimeoutError(f"{media_file.name} did not become ACTIVE in time.")

    print("\n⏳ Waiting for all uploads to become ACTIVE...")
    active_files = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(wait_until_active, g, f): (g, f) for g, f in uploaded_files}
        for fut in as_completed(futures):
            try:
                g, f = fut.result()
                active_files.append((g, f))
                print(f"✅ {f.name} is ACTIVE.")
            except Exception as e:
                print(f"❌ Activation failed: {e}")

    print(f"\n🚀 {len(active_files)} ACTIVE files, invoking Gemini once...")

    # --- Gemini call ---
    prompt = (
    "Act as a social media content analyst. Analyze ALL uploaded media and return a JSON array only. "
    "Do NOT include any explanations, text, or markdown. Return ONLY valid JSON. "
    "Each array element must be an object with these keys: "
    "media_group, main_topic, hook_transcript, hook_visual_elements, main_format, full_transcript. "
    "If a file is a PDF, treat each page as one carousel frame and merge the slides in one json. Divide the full transcript into slides accordingly. "
    "Output format example: "
    "[{\"media_group\": \"example\", \"main_topic\": \"topic\", \"hook_transcript\": \"...\", "
    "\"hook_visual_elements\": \"...\", \"main_format\": \"Reel\", \"full_transcript\": \"...\"}]"
)

    retries = 5
    raw_text = None
    for attempt in range(retries):
        try:
            print(f"🧠 Attempt {attempt + 1}/{retries} for Gemini...")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[f for _, f in active_files] + [prompt],
            )
            raw_text = response.text.strip()
            break
        except ServerError as e:
            if "503" in str(e):
                wait = 2 ** attempt
                print(f"⚠️ Gemini overloaded (503). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise e
    else:
        raise RuntimeError("❌ Gemini API failed after multiple attempts.")

    # --- JSON parsing helper ---
    def safe_json_parse(text):
        import re, json
        text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract the JSON array (most common)
        match = re.search(r"(\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Try to extract JSON object if it's not an array
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Try to remove Markdown code fences
        text = re.sub(r"```(?:json)?", "", text)
        text = text.replace("```", "")
        try:
            return json.loads(text.strip())
        except Exception:
            return None
    print(raw_text)
    parsed_json = safe_json_parse(raw_text)
    results = parsed_json if isinstance(parsed_json, list) else [{"error": "Invalid JSON output"}]

    # --- Cleanup ---
    print("\n🧹 Cleaning up uploaded files in parallel...")

    def delete_file(f):
        try:
            client.files.delete(name=f.name)
            return f.name, True, None
        except Exception as e:
            return f.name, False, str(e)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(delete_file, f) for _, f in active_files]
        for fut in as_completed(futures):
            name, success, err = fut.result()
            if success:
                print(f"🗑️ Deleted {name}")
            else:
                print(f"⚠️ Could not delete {name}: {err}")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    # --- Save results ---
    print(results) 


