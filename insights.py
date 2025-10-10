import requests
import json
import pandas as pd

def get_post_insights(user_token: str, ig_id: str, filename: str = "instagram_insights.csv", n: int = 100, export_format: str = "csv"):
    if not user_token:
        print("Missing access token.")
        return
    if not ig_id:
        print("Missing IG id.")
        return

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
    all_metrics = sorted(set(video_metrics + carousel_metrics))

    media_resp = requests.get(
        f"https://graph.facebook.com/v19.0/{ig_id}/media",
        params={
            "fields": "id,caption,timestamp,media_type,media_url,permalink",
            "limit": n,
            "access_token": user_token,
        },
        timeout=60
    ).json()

    media_list = media_resp.get("data", [])
    if not media_list:
        print("No media found for this Instagram account.")
        return

    results = []
    for idx, media in enumerate(media_list, start=1):
        media_id = media.get("id")
        caption = media.get("caption", "")
        ts = media.get("timestamp")
        mtype = media.get("media_type")
        media_url = media.get("media_url")
        permalink = media.get("permalink")

        if mtype in ("VIDEO", "REEL"):
            metrics = video_metrics
        elif mtype == "CAROUSEL_ALBUM" or mtype == "IMAGE":
            metrics = carousel_metrics
        else:
            metrics = video_metrics

        insights_resp = requests.get(
            f"https://graph.facebook.com/v19.0/{media_id}/insights",
            params={
                "metric": ",".join(metrics),
                "access_token": user_token,
            },
            timeout=30
        ).json()

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
            "media_url": media_url,
            "permalink": permalink,
            **insight_values
        }
        results.append(record)
        print(f"[{idx}/{len(media_list)}] Processed {media_id} ({mtype})")

    df = pd.DataFrame(results)
    if export_format == "json":
        json_filename = filename if filename.endswith(".json") else filename.rsplit(".", 1)[0] + ".json"
        df.to_json(json_filename, orient="records", force_ascii=False, indent=2)
        print(f"\n✅ Exported {len(results)} posts to {json_filename}")
    else:
        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"\n✅ Exported {len(results)} posts to {filename}")
    return df

def get_account_insights(user_token: str, ig_id: str, metrics=None, period: str = "day", since=None, until=None, date_preset=None, filename=None):
    if metrics is None:
        metrics = [
            "impressions", "reach", "profile_views",
            "website_clicks", "get_directions_clicks",
            "phone_call_clicks", "text_message_clicks",
            "accounts_engaged", "total_interactions", "follower_count"
        ]
    params = {"metric": ",".join(metrics), "period": period, "access_token": user_token}
    if date_preset:
        params["date_preset"] = date_preset
    else:
        import time
        if since is None and until is None and period == "day":
            until = int(time.time())
            since = until - 30 * 24 * 3600
        if since is not None: params["since"] = since
        if until is not None: params["until"] = until

    resp = requests.get(f"https://graph.facebook.com/v19.0/{ig_id}/insights", params=params, timeout=60)
    data = resp.json()
    if "error" in data:
        print("Error from Graph API:", data["error"])
        return None

    rows = []
    for metric_obj in data.get("data", []):
        name = metric_obj.get("name")
        period_out = metric_obj.get("period")
        values = metric_obj.get("values", [])
        if period_out == "day":
            for v in values:
                val = v.get("value")
                end_time = v.get("end_time")
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                rows.append({"ig_id": ig_id, "metric": name, "period": period_out, "end_time": end_time, "value": val})
        else:
            for v in values:
                val = v.get("value")
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                rows.append({"ig_id": ig_id, "metric": name, "period": period_out, "end_time": v.get("end_time"), "value": val})

    df = pd.DataFrame(rows)
    if filename:
        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"✅ Exported {len(df)} rows to {filename}")
    return df
