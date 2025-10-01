import os
import sys
import urllib.parse
import webbrowser
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# ---- Config ----
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://google.com/")

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")  # will hold user token in memory
IG_ID = None         # selected Instagram Business Account ID


# ---------------- OAuth Flow ----------------
def oauth_flow() -> str:
    """
    1) open OAuth dialog
    2) exchange code -> short-lived token
    3) exchange short-lived -> long-lived token
    Returns a usable user token.
    """
    if not APP_ID or not APP_SECRET or not REDIRECT_URI:
        print("Missing APP_ID, APP_SECRET or REDIRECT_URI. Set them in your .env.")
        sys.exit(1)

    scopes = [
        "instagram_basic",
        "instagram_manage_insights",
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_metadata",
    ]

    auth_url = (
        "https://www.facebook.com/v19.0/dialog/oauth?"
        f"client_id={APP_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        f"&scope={','.join(scopes)}"
        "&response_type=code"
        "&auth_type=rerequest"
        "&prompt=consent"
    )

    print("Open this URL and authorize the app:")
    print(auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    code = input("Paste the 'code' parameter from the redirect URL: ").strip()
    if not code:
        print("No code provided.")
        sys.exit(1)

    # Exchange code -> short-lived token
    token_url = (
        "https://graph.facebook.com/v19.0/oauth/access_token"
        f"?client_id={APP_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        f"&client_secret={APP_SECRET}"
        f"&code={code}"
    )
    short = requests.get(token_url, timeout=30).json()
    _print_json("Short-lived token response", short)
    access_token = short.get("access_token")
    if not access_token:
        print("Failed to obtain short-lived access token.")
        sys.exit(1)

    # Exchange short-lived -> long-lived
    long_token_url = (
        "https://graph.facebook.com/v19.0/oauth/access_token"
        f"?grant_type=fb_exchange_token"
        f"&client_id={APP_ID}"
        f"&client_secret={APP_SECRET}"
        f"&fb_exchange_token={access_token}"
    )
    long_data = requests.get(long_token_url, timeout=30).json()

    user_token = long_data.get("access_token") or access_token
    return user_token


# ---------------- IG Account Selection ----------------
def select_instagram_account(user_token: str):
    """
    Use debug_token to fetch granular_scopes and let user choose an IG account ID.
    Resolve each IG ID to its username for easier selection.
    """
    global IG_ID

    if not (APP_ID and APP_SECRET):
        print("APP_ID and APP_SECRET required for debug_token.")
        return

    app_token = f"{APP_ID}|{APP_SECRET}"
    resp = requests.get(
        "https://graph.facebook.com/debug_token",
        params={"input_token": user_token, "access_token": app_token},
        timeout=30
    ).json()

    data = resp.get("data", {})
    granular = data.get("granular_scopes", [])
    ig_ids = []

    for g in granular:
        if g.get("scope") == "instagram_manage_insights":
            ig_ids.extend(g.get("target_ids", []))

    if not ig_ids:
        print("No Instagram accounts found in granular_scopes. Check permissions.")
        return

    # Resolve each IG ID to username
    accounts = []
    for ig in ig_ids:
        info = requests.get(
            f"https://graph.facebook.com/v19.0/{ig}",
            params={"fields": "id,username", "access_token": user_token},
            timeout=30
        ).json()
        username = info.get("username", "Unknown")
        accounts.append({"id": ig, "username": username})

    print("\nAvailable Instagram Business Accounts:")
    for i, acct in enumerate(accounts, start=1):
        print(f"{i}. {acct['username']} ({acct['id']})")

    while True:
        try:
            sel = int(input("Select an account by number: ").strip())
            if 1 <= sel <= len(accounts):
                break
            print("Invalid selection.")
        except ValueError:
            print("Enter a number.")

    IG_ID = accounts[sel - 1]["id"]
    print(f"\nSelected Instagram Account: {accounts[sel - 1]['username']} ({IG_ID})")


# ---------------- IG Insights ----------------
import pandas as pd

def get_post_insights(user_token: str, ig_id: str, filename: str = "instagram_insights.csv"):
    """
    Fetch insights for the latest 100 media items of the given Instagram Business Account ID.
    Uses different metrics depending on media_type.
    Exports results to a CSV file.
    """
    if not user_token:
        print("Missing access token. Run option 1 first.")
        return
    if not ig_id:
        print("No Instagram account selected. Run option 3 first.")
        return

    # Metrics by media type
    video_metrics = [
        "views", "reach", "saved", "likes",
        "comments", "shares",
        "ig_reels_video_view_total_time", "ig_reels_avg_watch_time"
    ]

    carousel_metrics = [
        "views", "reach", "replies", "saved",
        "likes", "comments", "shares",
        "follows", "profile_visits", "profile_activity", "navigation"
    ]

    # Union of all metrics (for consistent CSV columns)
    all_metrics = sorted(set(video_metrics + carousel_metrics))

    # 1) Get latest 100 media
    media_resp = requests.get(
        f"https://graph.facebook.com/v19.0/{ig_id}/media",
        params={
            "fields": "id,caption,timestamp,media_type,media_url,permalink",
            "limit": 100,
            "access_token": user_token,
        },
        timeout=60
    ).json()

    media_list = media_resp.get("data", [])
    if not media_list:
        print("No media found for this Instagram account.")
        return

    results = []

    # 2) For each media, fetch insights with proper metrics
    for idx, media in enumerate(media_list, start=1):
        media_id = media.get("id")
        caption = media.get("caption", "")
        ts = media.get("timestamp")
        mtype = media.get("media_type")
        media_url = media.get("media_url")
        permalink = media.get("permalink")

        # Decide metrics based on media_type
        if mtype in ("VIDEO", "REEL"):
            metrics = video_metrics
        elif mtype == "CAROUSEL_ALBUM" or mtype == "IMAGE":
            metrics = carousel_metrics
        else:
            # Default: try video metrics
            metrics = video_metrics

        insights_resp = requests.get(
            f"https://graph.facebook.com/v19.0/{media_id}/insights",
            params={
                "metric": ",".join(metrics),
                "access_token": user_token,
            },
            timeout=30
        ).json()

        # normalize results
        insight_values = {m: None for m in all_metrics}
        for item in insights_resp.get("data", []):
            name = item.get("name")
            values = item.get("values", [])
            if values:
                insight_values[name] = values[-1].get("value")

        record = {
            "media_id": media_id,
            "caption": caption.replace("\n", " ")[:200],
            "timestamp": ts,
            "media_type": mtype,
            "media_url":media_url,
            "permalink":permalink,
            **insight_values
        }
        results.append(record)
        print(f"[{idx}/{len(media_list)}] Processed {media_id} ({mtype})")

    # 3) Export to CSV
    df = pd.DataFrame(results)
    df.to_csv(filename, index=False, encoding="utf-8-sig")

    print(f"\n✅ Exported {len(results)} posts to {filename}")
    return df

def get_account_insights(
    user_token: str,
    ig_id: str,
    metrics: list[str] | None = None,
    period: str = "day",                 # "day" or "lifetime"
    since: int | None = None,            # UNIX seconds; use with period="day"
    until: int | None = None,            # UNIX seconds; use with period="day"
    date_preset: str | None = None,      # e.g. "last_30_days", "last_7_days"
    filename: str | None = None          # e.g. "account_insights.csv" to export
):
    """
    Calls: GET /{ig-user-id}/insights
    Returns a normalized list of rows = one row per metric datapoint (time bucket or lifetime).
    Docs: https://developers.facebook.com/docs/instagram-platform/api-reference/instagram-user/insights/
    """

    if not user_token:
        print("Missing access token. Run OAuth first.")
        return None
    if not ig_id:
        print("Missing IG user id. Select an account first.")
        return None

    # Sensible defaults if not provided
    if metrics is None:
        # Common account-level metrics you likely want for day period:
        metrics = [
            "impressions", "reach", "profile_views",
            "website_clicks", "get_directions_clicks",
            "phone_call_clicks", "text_message_clicks",
            "accounts_engaged", "total_interactions", "follower_count"
        ]
        # For lifetime period you might instead pass things like:
        # ["audience_city","audience_country","audience_gender_age","audience_locale","online_followers"]

    params = {
        "metric": ",".join(metrics),
        "period": period,
        "access_token": user_token,
    }
    # Time range handling
    if date_preset:
        params["date_preset"] = date_preset
    else:
        if since is None and until is None and period == "day":
            # default last 30 days if none provided
            until = int(time.time())
            since = until - 30 * 24 * 3600
        if since is not None: params["since"] = since
        if until is not None: params["until"] = until

    resp = requests.get(
        f"https://graph.facebook.com/v19.0/{ig_id}/insights",
        params=params,
        timeout=60
    )
    data = resp.json()

    # Show raw in case of debugging
    # print(json.dumps(data, indent=2))

    if "error" in data:
        print("Error from Graph API:", data["error"])
        return None

    # Normalize
    rows = []
    for metric_obj in data.get("data", []):
        name = metric_obj.get("name")
        period_out = metric_obj.get("period")
        values = metric_obj.get("values", [])

        # For "day" metrics, values is an array of {value, end_time}
        # For "lifetime" audience metrics, value is often an object (dict of buckets)
        if period_out == "day":
            for v in values:
                val = v.get("value")
                end_time = v.get("end_time")
                # Some metrics may return dict even in day (rare) — stringify for CSV
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                rows.append({
                    "ig_id": ig_id,
                    "metric": name,
                    "period": period_out,
                    "end_time": end_time,
                    "value": val
                })
        else:
            # lifetime or other periods
            # Usually a single latest object in values; keep as JSON string if object
            for v in values:
                val = v.get("value")
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                rows.append({
                    "ig_id": ig_id,
                    "metric": name,
                    "period": period_out,
                    "end_time": v.get("end_time"),
                    "value": val
                })

    # Export (optional)
    df = pd.DataFrame(rows)
    if filename:
        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"✅ Exported {len(df)} rows to {filename}")

    return df



# ---------------- Media Download ----------------
def download_last_n_media(user_token: str, ig_id: str, n: int = 10, folder: str = "media"):
    """
    Download the last n media (video or image) for the given Instagram Business Account ID.
    """
    if not user_token:
        print("Missing access token. Run option 1 first.")
        return
    if not ig_id:
        print("No Instagram account selected. Run option 2 first.")
        return

    # 1) Get latest n media
    media_resp = requests.get(
        f"https://graph.facebook.com/v19.0/{ig_id}/media",
        params={
            "fields": "id,media_type,media_url",
            "limit": n,
            "access_token": user_token,
        },
        timeout=60
    ).json()

    media_list = media_resp.get("data", [])
    if not media_list:
        print("No media found for this Instagram account.")
        return

    if not os.path.exists(folder):
        os.makedirs(folder)

    for idx, media in enumerate(media_list, start=1):
        media_url = media.get("media_url")
        media_type = media.get("media_type")
        media_id = media.get("id")
        if not media_url or media_type not in ("IMAGE", "VIDEO"):
            continue
        ext = "mp4" if media_type == "VIDEO" else "jpg"
        filename = f"{media_id}.{ext}"
        filepath = os.path.join(folder, filename)
        try:
            with requests.get(media_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(filepath, "wb") as f:
                    import shutil
                    shutil.copyfileobj(r.raw, f)
            print(f"Downloaded {filename}")
        except Exception as e:
            print(f"Failed to download {media_url}: {e}")


# ---------------- Menu ----------------
def main_menu():
    global ACCESS_TOKEN, IG_ID

    while True:
        print("\nChoose an option:")
        print("1. Get USER access token")
        print("2. Select Instagram account")
        print("3. Get post insights")
        print("4. Download media")
        print("0. Exit")

        choice = input("Enter 0,1,2,3,4: ").strip()

        if choice == "1":
            ACCESS_TOKEN = oauth_flow()
            print("Stored USER token (in memory).")

        elif choice == "3":
            get_post_insights(ACCESS_TOKEN, IG_ID)

        elif choice == "2":
            if not ACCESS_TOKEN:
                print("No USER token. Run option 1 first.")
            else:
                select_instagram_account(ACCESS_TOKEN)

        elif choice == "4":
            if not ACCESS_TOKEN or not IG_ID:
                print("You need to get a token and select an account first.")
            else:
                try:
                    n = int(input("How many recent media do you want to download? "))
                    download_last_n_media(ACCESS_TOKEN, IG_ID, n=n, folder="media")
                except Exception as e:
                    print(f"Invalid input: {e}")

        elif choice == "0":
            print("Bye!")
            break

        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main_menu()
