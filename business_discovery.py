import requests

def get_ig_id_from_username_business_discovery(
    username: str, ig_id: str, user_token: str, n: int = 10, version: str = "v24.0"
):
    # --- Request both parent media and any nested children inline ---
    fields = (
        f"business_discovery.username({username})"
        + "{id,username,followers_count,media_count,"
        + f"media.limit({n}){{"
        + "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,"
        + "like_count,comments_count,view_count,"
        + "children{id,media_type,media_url,thumbnail_url,permalink}"
        + "}}"
    )

    url = f"https://graph.facebook.com/{version}/{ig_id}"
    params = {"fields": fields, "access_token": user_token}

    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
    except Exception as e:
        print(f"Failed to call or parse response from Graph API: {e}")
        return None, []

    if "error" in data:
        err = data["error"]
        print(f"API Error {err.get('code')} ({err.get('type')}): {err.get('message')}")
        return None, []

    bd = data.get("business_discovery")
    if not bd:
        print("No business_discovery object found — likely missing permissions.")
        return None, []

    target_ig_id = bd.get("id")
    media_list = bd.get("media", {}).get("data", [])
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
            "media_id": media.get("id"),
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
