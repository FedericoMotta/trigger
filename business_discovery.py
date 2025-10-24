import requests

import requests
from time import sleep

def get_ig_id_from_username_business_discovery(
    username: str,
    ig_id: str,
    user_token: str,
    n: int = 100,
    version: str = "v24.0",
):
    """
    Fetch up to `n` media for a given username via Business Discovery.
    Handles pagination (50 media max per request).
    Returns: (target_ig_id, media_list)
    """

    base_url = f"https://graph.facebook.com/{version}/{ig_id}"
    all_media = []
    after = None
    target_ig_id = None

    while len(all_media) < n:
        limit = min(50, n - len(all_media))

        # Build fields with optional pagination cursor
        media_pagination = f"media.limit({limit})" + (f".after({after})" if after else "")
        fields = (
            f"business_discovery.username({username})" + "{"
            "id,username,followers_count,media_count,"
            f"{media_pagination}{{"
            "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,"
            "like_count,comments_count,view_count,"
            "children{id,media_type,media_url,thumbnail_url,permalink}"
            "}}"
        )

        params = {"fields": fields, "access_token": user_token}

        try:
            resp = requests.get(base_url, params=params, timeout=30)
            data = resp.json()
        except Exception as e:
            print(f"Failed to call or parse response from Graph API: {e}")
            break

        if "error" in data:
            err = data["error"]
            print(f"API Error {err.get('code')} ({err.get('type')}): {err.get('message')}")
            break

        bd = data.get("business_discovery")
        if not bd:
            print("No business_discovery object found — likely missing permissions.")
            break

        # Extract IG ID and media list
        target_ig_id = bd.get("id", target_ig_id)
        media_data = bd.get("media", {}).get("data", [])
        if not media_data:
            break

        all_media.extend(media_data)

        # Pagination
        paging = bd.get("media", {}).get("paging", {})
        after = paging.get("cursors", {}).get("after")
        if not after:
            break

        sleep(0.3)  # small delay to respect rate limits

    # Trim in case we got more than requested
    media_list = all_media[:n]
    print(f"Fetched {len(media_list)} media items for @{username}.")
    return target_ig_id, media_list


def get_insights_for_profile_business_discovery(
    user_token: str, ig_id: str, username: str, n: int = 10, export_format: str = "csv"
):
    target_ig_id, media_list = get_ig_id_from_username_business_discovery(
        username, ig_id, user_token, n=n
    )

    if not media_list:
        print("No media found or unable to access business_discovery.")
        return None

    results = []
    for media in media_list:
        record = {
            "id": media.get("id"),
            "caption": (media.get("caption") or "").replace("\n", " ")[:200],
            "timestamp": media.get("timestamp"),
            "media_type": media.get("media_type"),
            "media_url": media.get("media_url") or media.get("thumbnail_url"),
            "permalink": media.get("permalink"),
            "like_count": media.get("like_count"),
            "comments_count": media.get("comments_count"),
            "view_count": media.get("view_count"),
        }

        # --- Add carousel children inline ---
        children = media.get("children", {}).get("data", [])
        if children:
            record["children"] = [
                {
                    "id": c.get("id"),
                    "media_type": c.get("media_type"),
                    "media_url": c.get("media_url") or c.get("thumbnail_url"),
                    "permalink": c.get("permalink"),
                }
                for c in children
            ]
        else:
            record["children"] = []

        results.append(record)

    return results
