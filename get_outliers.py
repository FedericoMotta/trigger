from business_discovery import get_ig_id_from_username_business_discovery
from downloads import download_media_from_list
from insights import get_post_insights
import requests
import os
import re
from PIL import Image
from collections import defaultdict
from google import genai
from google.genai.errors import ServerError
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json
from insights import get_post_insights
import subprocess

def get_outliers(user_token, ig_id, username, n_media, multiplier):
    folder = f"outlier_media/{username}"
    
    # Check if media already exists in the folder FIRST
    media_exts = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".pdf", ".webp"}
    has_existing_media = False
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in media_exts:
                has_existing_media = True
                break

    skip_download = False
    if has_existing_media:
        try:
            answer = input(f"Found existing media in '{folder}'. Do you want to download again? (y/N): ").strip().lower()
        except Exception:
            answer = "n"
        if answer not in ("y", "yes"):
            skip_download = True
            print("Skipping download; using existing media.")

    # Check if the username matches the authenticated account
    resp = requests.get(
        f"https://graph.facebook.com/v19.0/{ig_id}",
        params={"fields": "username", "access_token": user_token},
        timeout=20,
    )
    own_username = resp.json().get("username")
    search_type = "other"
    own_content = False
    if username == own_username:
        own_content = True
        search_type = "own"
        print(f"Analyzing your own profile ({username}) with detailed insights...")
        df = get_post_insights(user_token, ig_id, n=n_media, export_format="json", username=username)
        media_list = df.to_dict('records')
        average_likes = (sum(item.get("likes") or 0 for item in media_list)/ len(media_list) if media_list else 0)
        outliers = [item for item in media_list if (item.get("likes") or 0) > multiplier * average_likes]
    else:
        print(f"Analyzing profile {username} with business discovery...")
        target_ig_id, media_list = get_ig_id_from_username_business_discovery(username, ig_id, user_token, n=n_media)
        average_likes = (sum(item.get("like_count") or 0 for item in media_list)/ len(media_list) if media_list else 0)
        outliers = [item for item in media_list if (item.get("like_count") or 0) > multiplier * average_likes]

    print(f"Found {len(outliers)} outlier posts with more than double the average likes ({average_likes:.2f})")
    
    # Only download if user confirmed or no existing media
    if not skip_download:
        download_media_from_list(outliers, n=len(outliers), folder=folder, user_token=user_token)

    analyze_all_media(
        media_dir=folder,
        output_path=f"{folder}/{username}_outlier_media_results.json",
        media_list=media_list,
        max_workers=5,
        own_content=own_content,
        username=username  # Pass username to analyze_all_media
    )


def merge_images_to_pdf(image_paths, output_path):
    """Merge multiple images into a single multi-page PDF."""
    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    imgs[0].save(output_path, save_all=True, append_images=imgs[1:])
    return output_path


def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe, fallback to moviepy if available."""
    # Primary: ffprobe (robust csv output)
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout:
            try:
                return float(result.stdout.strip())
            except Exception:
                pass
    except Exception as e:
        # fall through to fallback attempts
        pass


    # Could not determine duration
    print(f"⚠️ Could not determine duration for {video_path} (ffprobe/moviepy unavailable or failed).")
    return None

def analyze_all_media(media_dir="outlier_media/", output_path="outlier_media_results.json", media_list=None, max_workers=5, own_content=False, username=None):
    if media_list is None:
        media_list = []

    client = genai.Client()

    def get_carousel_prefix(filename):
        # Match pattern: parentID_childID.ext -> return parentID
        match = re.match(r"^(\d{5,})_\d+\.[^.]+$", filename)
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

    # Build carousel_children map and order map BEFORE merge loop
    carousel_children_map = {}
    carousel_order_map = {}  # media_id -> {child_id: position_index}
    
    for item in media_list:
        item_id = str(item.get("id", item.get("media_id", "")))
        children = item.get("children", {}).get("data", [])
        if children:
            carousel_children_map[item_id] = [child.get("media_url", "") for child in children]
            carousel_order_map[item_id] = {str(child.get("id", "")): idx for idx, child in enumerate(children)}

    # --- Merge carousels into PDFs (sort slides by API position) ---
    prepared_files = []
    
    for group_name, files in carousel_groups.items():
        media_id_match = re.findall(r"\d{5,}", group_name)
        media_id = media_id_match[0] if media_id_match else group_name

        if len(files) > 1 and all(os.path.splitext(f)[1].lower() in image_exts for f in files):
            # Sort by API-provided position (from carousel_order_map)
            def get_api_position(path):
                basename = os.path.basename(path)
                match = re.search(r"_(\d+)\.[^.]+$", basename)
                child_id = match.group(1) if match else None
                if media_id in carousel_order_map and child_id in carousel_order_map[media_id]:
                    return carousel_order_map[media_id][child_id]
                return 999  # fallback for unknown children
            
            files_sorted = sorted(files, key=get_api_position)
            pdf_path = os.path.join(media_dir, f"{group_name}.pdf")
            merge_images_to_pdf(files_sorted, pdf_path)
            prepared_files.append((media_id, group_name, pdf_path))
            print(f"📄 Merged carousel '{group_name}' into {os.path.basename(pdf_path)} (ID: {media_id}, {len(files_sorted)} slides in API order)")
        else:
            prepared_files.append((media_id, group_name, files[0]))

    print(f"📁 Ready to upload {len(prepared_files)} files (after merging carousels).")

    # --- Upload all files in parallel ---
    def upload_file(media_id, group_name, path):
        try:
            media_file = client.files.upload(file=path)
            return media_id, group_name, path, media_file
        except Exception as e:
            print(f"❌ Upload failed for {path}: {e}")
            return media_id, group_name, path, None

    print(f"🚀 Uploading in parallel (max {max_workers} workers)...")
    uploaded_files = []
    
    # Filter out videos longer than 3 minutes before uploading
    files_to_upload = []
    for media_id, group_name, path in prepared_files:
        ext = os.path.splitext(path)[1].lower()
        if ext in {".mp4", ".mov"}:
            duration = get_video_duration(path)
            if duration is None or duration > 180:
                # Skip if unknown or > 3 min
                print(f"⏭️ Skipped {os.path.basename(path)} (duration check failed or > 3 min)")
                continue
        files_to_upload.append((media_id, group_name, path))
    
    print(f"📊 Total prepared: {len(prepared_files)}, Uploading: {len(files_to_upload)}")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(upload_file, m, g, p): (m, g, p) for m, g, p in files_to_upload}
        for fut in as_completed(futures):
            media_id, group_name, path, media_file = fut.result()
            if media_file:
                uploaded_files.append((media_id, group_name, path, media_file))
                print(f"✅ Uploaded {os.path.basename(path)}")
            else:
                msg = f"⚠️ Skipped {os.path.basename(path)} due to upload error."
                print(msg)

    # --- Wait for all to become ACTIVE ---
    def wait_until_active(media_id, group_name, path, media_file, retries=20, delay=2):
        for _ in range(retries):
            file_info = client.files.get(name=media_file.name)
            if file_info.state.name == "ACTIVE":
                return media_id, group_name, path, media_file
            elif file_info.state.name == "FAILED":
                raise RuntimeError(f"{media_file.name} failed to process.")
            time.sleep(delay)
        raise TimeoutError(f"{media_file.name} did not become ACTIVE in time.")

    print("\n⏳ Waiting for all uploads to become ACTIVE...")
    active_files = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(wait_until_active, m, g, p, f): (m, g, p, f) for m, g, p, f in uploaded_files}
        for fut in as_completed(futures):
            try:
                m, g, p, f = fut.result()
                active_files.append((m, g, p, f))
                print(f"✅ {os.path.basename(p)} is ACTIVE.")
            except Exception as e:
                print(f"❌ Activation failed: {e}")

    print(f"\n🚀 {len(active_files)} ACTIVE files, invoking Gemini once...")

    # --- Gemini prompt ---
    prompt = (
        "Act as a social media content analyst. Analyze ALL uploaded media and return ONLY a valid JSON array. "
        "Each element object keys: media_id, main_topic, hook_transcript, hook_visual_elements, format, format_main_elements, full_transcript. "
        "For PDFs treat pages as carousel frames merged into one entry. Output only JSON."
    )

    # --- Call Gemini with retry logic ---
    retries = 5
    raw_text = None
    for attempt in range(retries):
        try:
            print(f"🧠 Attempt {attempt + 1}/{retries} for Gemini...")
            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[f for _, _, _, f in active_files] + [prompt],
            )
            print("🧩 Gemini raw response:", response)
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
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"(\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        text = re.sub(r"```(?:json)?", "", text)
        text = text.replace("```", "")
        try:
            return json.loads(text.strip())
        except Exception:
            return None

    parsed_json = safe_json_parse(raw_text)
    results = parsed_json if isinstance(parsed_json, list) else [{"error": "Invalid JSON output"}]

    # --- Assign media_ids (removed validation prints) ---
    for i, entry in enumerate(results):
        if i < len(active_files):
            entry["media_id"] = str(active_files[i][0])
        entry["username"] = username  # Add username to every entry

    media_lookup = {str(item.get("id", item.get("media_id", ""))): item for item in media_list}

    if own_content:
        for entry in results:
            media_id = entry.get("media_id", "")
            meta = media_lookup.get(media_id)
            if meta:
                entry["like_count"] = meta.get("like_count", meta.get("likes", 0))
                entry["view_count"] = meta.get("view_count", meta.get("views", 0))
                entry["comments_count"] = meta.get("comments_count", meta.get("comments", 0))
                entry["caption"] = meta.get("caption", "")
                entry["media_type"] = meta.get("media_type", "")
                
                # For carousels, use carousel_slides instead of single media_url
                if media_id in carousel_children_map:
                    entry["carousel_slides"] = carousel_children_map[media_id]
                    # Remove or set media_url to empty since carousel has multiple URLs
                    entry["media_url"] = ""
                else:
                    entry["media_url"] = meta.get("media_url", "")
                
                entry["thumbnail_url"] = meta.get("thumbnail_url", "")
                entry["permalink"] = meta.get("permalink", "")
                entry["shares"] = meta.get("shares", 0)
                entry["saves"] = meta.get("saved", 0)
                entry["reach"] = meta.get("reach", 0)
                entry["profile_visits"] = meta.get("profile_visits", 0)
                entry["follows"] = meta.get("follows", 0)
                entry["replies"] = meta.get("replies", 0)
                entry["video_view_total_time"] = meta.get("ig_reels_video_view_total_time", 0)
                entry["avg_watch_time"] = meta.get("ig_reels_avg_watch_time", 0)
            else:
                entry.setdefault("like_count", 0)
                entry.setdefault("view_count", 0)
                entry.setdefault("comments_count", 0)
                entry.setdefault("shares", 0)
                entry.setdefault("saves", 0)
                entry.setdefault("reach", 0)
                entry.setdefault("profile_visits", 0)
                entry.setdefault("follows", 0)
                entry.setdefault("replies", 0)
                entry.setdefault("video_view_total_time", 0)
                entry.setdefault("avg_watch_time", 0)
                entry.setdefault("caption", "")
    else:
        for entry in results:
            media_id = entry.get("media_id", "")
            meta = media_lookup.get(media_id)
            if meta:
                entry["like_count"] = meta.get("like_count", 0)
                entry["view_count"] = meta.get("view_count", 0)
                entry["comments_count"] = meta.get("comments_count", 0)
                entry["caption"] = meta.get("caption", "")
                entry["media_type"] = meta.get("media_type", "")
                
                # For carousels, use carousel_slides instead of single media_url
                if media_id in carousel_children_map:
                    entry["carousel_slides"] = carousel_children_map[media_id]
                    entry["media_url"] = ""
                else:
                    entry["media_url"] = meta.get("media_url", "")
                
                entry["thumbnail_url"] = meta.get("thumbnail_url", "")
                entry["permalink"] = meta.get("permalink", "")
            else:
                entry.setdefault("like_count", 0)
                entry.setdefault("view_count", 0)
                entry.setdefault("comments_count", 0)
                entry.setdefault("caption", "")

    # ...existing code (cleanup uploads)...

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Analysis complete. Results saved to: {output_path}")