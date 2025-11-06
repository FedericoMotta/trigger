import os
import requests

from business_discovery import get_ig_id_from_username_business_discovery
from accounts import extract_username_from_url


def _fetch_children(media_id: str, user_token: str):
    """
    Return list of child dicts with keys: {'id','media_type','media_url'}.
    Tries parent.children, then per-child node requests, then /{media_id}/children fallback.
    """
    try:
        resp = requests.get(
            f"https://graph.facebook.com/v19.0/{media_id}",
            params={"fields": "children{ id,media_type,media_url,thumbnail_url }", "access_token": user_token},
            timeout=30
        ).json()
    except Exception:
        resp = {}

    children = resp.get("children", {}).get("data", []) or []
    enriched = []
    for child in children:
        child_id = child.get("id")
        media_url = child.get("media_url")
        media_type = (child.get("media_type") or "").upper()
        if not media_url and child_id:
            try:
                c = requests.get(
                    f"https://graph.facebook.com/v19.0/{child_id}",
                    params={"fields": "media_type,media_url,thumbnail_url", "access_token": user_token},
                    timeout=30
                ).json()
                media_url = c.get("media_url") or c.get("thumbnail_url")
                media_type = (c.get("media_type") or media_type).upper()
            except Exception:
                pass
        enriched.append({"id": child_id, "media_type": media_type, "media_url": media_url})

    if not enriched:
        try:
            resp2 = requests.get(
                f"https://graph.facebook.com/v19.0/{media_id}/children",
                params={"fields": "id,media_type", "access_token": user_token},
                timeout=30
            ).json()
            list_children = resp2.get("data", []) or []
            for ch in list_children:
                cid = ch.get("id")
                c_media_type = (ch.get("media_type") or "").upper()
                c_media_url = None
                if cid:
                    try:
                        c = requests.get(
                            f"https://graph.facebook.com/v19.0/{cid}",
                            params={"fields": "media_url,thumbnail_url,media_type", "access_token": user_token},
                            timeout=30
                        ).json()
                        c_media_url = c.get("media_url") or c.get("thumbnail_url")
                        c_media_type = (c.get("media_type") or c_media_type).upper()
                    except Exception:
                        pass
                enriched.append({"id": cid, "media_type": c_media_type, "media_url": c_media_url})
        except Exception:
            pass

    return enriched


def download_last_n_media(user_token: str, ig_id: str, n: int = 10, folder: str = "media"):
    """
    Download the last n media (including carousel children) for the given IG account (owned media).
    """
    if not user_token or not ig_id:
        print("Missing token or ig_id.")
        return

    media_resp = requests.get(
        f"https://graph.facebook.com/v19.0/{ig_id}/media",
        params={"fields": "id,media_type,media_url,children{ id,media_type,media_url }", "limit": n, "access_token": user_token},
        timeout=60
    ).json()
    media_list = media_resp.get("data", [])
    if not media_list:
        print("No media found.")
        return

    os.makedirs(folder, exist_ok=True)
    for idx, media in enumerate(media_list, start=1):
        media_id = media.get("id")
        media_type = (media.get("media_type") or "").upper()

        if media_type == "CAROUSEL_ALBUM":
            children = media.get("children", {}).get("data", []) or _fetch_children(media_id, user_token)
            if not children:
                print(f"[{idx}/{len(media_list)}] No children found for carousel {media_id}, skipping.")
                continue

            for c_idx, child in enumerate(children, start=1):
                child_id = child.get("id")
                media_url = child.get("media_url")
                child_type = (child.get("media_type") or "").upper()
                if not media_url:
                    try:
                        mresp = requests.get(
                            f"https://graph.facebook.com/v19.0/{child_id}",
                            params={"fields": "media_type,media_url,thumbnail_url", "access_token": user_token},
                            timeout=30
                        ).json()
                        media_url = mresp.get("media_url") or mresp.get("thumbnail_url")
                        child_type = (mresp.get("media_type") or child_type).upper()
                    except Exception:
                        media_url = None

                if not media_url:
                    print(f"[{idx}/{len(media_list)}][{c_idx}/{len(children)}] Skipping child {child_id}: no media_url")
                    continue

                ext = "mp4" if child_type in ("VIDEO", "REEL") else "jpg"
                filename = f"{media_id}_{child_id}.{ext}"
                filepath = os.path.join(folder, filename)
                try:
                    with requests.get(media_url, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        import shutil
                        with open(filepath, "wb") as f:
                            shutil.copyfileobj(r.raw, f)
                    print(f"[{idx}/{len(media_list)}][{c_idx}/{len(children)}] Downloaded {filename}")
                except Exception as e:
                    print(f"[{idx}/{len(media_list)}][{c_idx}/{len(children)}] Failed to download {media_url}: {e}")
            continue

        media_url = media.get("media_url")
        if not media_url:
            try:
                mresp = requests.get(
                    f"https://graph.facebook.com/v19.0/{media_id}",
                    params={"fields": "media_url,thumbnail_url,media_type", "access_token": user_token},
                    timeout=30
                ).json()
                media_url = mresp.get("media_url") or mresp.get("thumbnail_url")
                media_type = (mresp.get("media_type") or media_type).upper()
            except Exception:
                media_url = None

        if not media_url:
            print(f"[{idx}/{len(media_list)}] Skipping {media_id}: no media_url")
            continue

        ext = "mp4" if media_type in ("VIDEO", "REEL") else "jpg"
        filename = f"{media_id}.{ext}"
        filepath = os.path.join(folder, filename)
        try:
            with requests.get(media_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                import shutil
                with open(filepath, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
            print(f"Downloaded {filename}")
        except Exception as e:
            print(f"Failed to download {media_url}: {e}")


def download_media_from_profile_business_discovery(user_token: str, ig_id: str, profile_url: str, n: int = 5, folder: str = "media"):
    """
    Download last n media from a profile discovered via Business Discovery (not owned).
    """
    if not user_token or not ig_id:
        print("Missing token or ig_id.")
        return

    username = extract_username_from_url(profile_url)
    if not username:
        print("Could not extract username from URL.")
        return

    target_ig_id, media_list = get_ig_id_from_username_business_discovery(username, ig_id, user_token, n=n)
    if not media_list:
        print("No media available for that profile.")
        return

    os.makedirs(folder, exist_ok=True)
    print(media_list)
    download_media_from_list(media_list, n, folder)

def download_media_from_list(media_list, n, folder, user_token):
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        for idx, media in enumerate(media_list[:n], start=1):
            media_id = media.get("id", media.get("media_id"))
            media_type = (media.get("media_type") or "").upper()

            if media_type == "CAROUSEL_ALBUM":
                children = media.get("children", {}).get("data", []) or _fetch_children(media_id, user_token)
                if not children:
                    print(f"[{idx}/{min(n,len(media_list))}] No children found for carousel {media_id}, skipping.")
                    continue

                for c_idx, child in enumerate(children, start=1):
                    child_id = child.get("id")
                    media_url = child.get("media_url")
                    child_type = (child.get("media_type") or "").upper()
                    if not media_url:
                        try:
                            mresp = requests.get(
                                f"https://graph.facebook.com/v19.0/{child_id}",
                                params={"fields": "media_type,media_url,thumbnail_url", "access_token": user_token},
                                timeout=30
                            ).json()
                            media_url = mresp.get("media_url") or mresp.get("thumbnail_url")
                            child_type = (mresp.get("media_type") or child_type).upper()
                        except Exception:
                            media_url = None

                    if not media_url:
                        print(f"[{idx}/{min(n,len(media_list))}][{c_idx}/{len(children)}] Skipping child {child_id}: no media_url")
                        continue

                    ext = "mp4" if child_type in ("VIDEO", "REEL") else "jpg"
                    filename = f"{media_id}_{child_id}.{ext}"
                    filepath = os.path.join(folder, filename)
                    try:
                        with requests.get(media_url, stream=True, timeout=60) as r:
                            r.raise_for_status()
                            import shutil
                            with open(filepath, "wb") as f:
                                shutil.copyfileobj(r.raw, f)
                        print(f"[{idx}/{min(n,len(media_list))}][{c_idx}/{len(children)}] Saved {filename}")
                    except Exception as e:
                        print(f"[{idx}/{min(n,len(media_list))}][{c_idx}/{len(children)}] Failed to download {media_url}: {e}")
                continue

            media_url = media.get("media_url")
            if not media_url:
                try:
                    mresp = requests.get(
                        f"https://graph.facebook.com/v19.0/{media_id}",
                        params={"fields": "media_url,thumbnail_url,media_type", "access_token": user_token},
                        timeout=30
                    ).json()
                    media_url = mresp.get("media_url") or mresp.get("thumbnail_url")
                    media_type = (mresp.get("media_type") or media_type).upper()
                except Exception:
                    media_url = None

            if not media_url:
                print(f"[{idx}/{min(n,len(media_list))}] Skipping {media_id}: no media_url")
                continue

            ext = "mp4" if media_type in ("VIDEO", "REEL") else "jpg"
            filename = f"{media_id}.{ext}"
            filepath = os.path.join(folder, filename)
            try:
                with requests.get(media_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    import shutil
                    with open(filepath, "wb") as f:
                        shutil.copyfileobj(r.raw, f)
                print(f"[{idx}/{min(n,len(media_list))}] Saved {filename}")
            except Exception as e:
                print(f"[{idx}/{min(n,len(media_list))}] Failed to download {media_url}: {e}")