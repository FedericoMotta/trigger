import requests
import json
import pandas as pd
import os
from pathlib import Path

def _get_insights_dir():
    base = Path(__file__).resolve().parent
    insights_dir = base / "insights"
    insights_dir.mkdir(parents=True, exist_ok=True)
    return insights_dir

def get_post_insights(user_token: str, ig_id: str, filename: str = "instagram_insights.csv", n: int = 100, export_format: str = "csv", username: str | None = None):
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
        "follows", "profile_visits",
    ]
    # union of metrics for batch request
    all_metrics = sorted(set(video_metrics + carousel_metrics))
    metrics_param = ",".join(all_metrics)

    # 1) Get latest n media (basic fields)
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

    # Helper: chunk ids to avoid overly long URLs
    def chunks(lst, size):
        for i in range(0, len(lst), size):
            yield lst[i:i + size]

    media_ids = [m.get("id") for m in media_list if m.get("id")]
    batch_size = 50

    processed = 0
    for batch in chunks(media_ids, batch_size):
        ids_str = ",".join(batch)
        # Request media fields + insights for the whole batch
        params = {
            "ids": ids_str,
            "fields": f"caption,timestamp,media_type,media_url,permalink,insights.metric({metrics_param})",
            "access_token": user_token,
        }
        try:
            batch_resp = requests.get("https://graph.facebook.com/v19.0/", params=params, timeout=90).json()
        except Exception as e:
            print(f"Batch request failed for ids {ids_str[:200]}...: {e}")
            continue

        if "error" in batch_resp:
            print("API Error:", batch_resp["error"])
            continue

        # batch_resp is a mapping { media_id: { fields... }, ... }
        for media_id in batch:
            media_data = batch_resp.get(media_id) or {}
            caption = media_data.get("caption", "")
            ts = media_data.get("timestamp")
            mtype = media_data.get("media_type")
            media_url = media_data.get("media_url")
            permalink = media_data.get("permalink")

            # Normalize insight values (use all_metrics union)
            insight_values = {m: None for m in all_metrics}
            insights_obj = media_data.get("insights", {}).get("data", [])
            for item in insights_obj:
                name = item.get("name")
                values = item.get("values", [])
                if values:
                    insight_values[name] = values[-1].get("value")

            record = {
                "media_id": media_id,
                "caption": (caption or "").replace("\n", " ")[:200],
                "timestamp": ts,
                "media_type": mtype,
                "media_url": media_url,
                "permalink": permalink,
                **insight_values
            }
            results.append(record)
            processed += 1
            print(f"[{processed}/{len(media_ids)}] Processed {media_id} ({mtype})")

    # 3) Export to CSV or JSON into insights/ folder
    df = pd.DataFrame(results)
    insights_dir = _get_insights_dir()

    # build output filename: if username provided use "{username}_insights", else use provided filename
    if username:
        base_name = f"{username}_insights"
        if export_format == "json":
            out_filename = base_name + ".json"
        else:
            out_filename = base_name + ".csv"
    else:
        # respect provided filename
        if export_format == "json":
            out_filename = filename if filename.endswith(".json") else Path(filename).with_suffix(".json").name
        else:
            out_filename = filename if filename.endswith(".csv") else Path(filename).with_suffix(".csv").name

    out_path = insights_dir / out_filename

    if export_format == "json":
        df.to_json(out_path, orient="records", force_ascii=False, indent=2)
        print(f"\n✅ Exported {len(results)} posts to {out_path}")
    else:
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"\n✅ Exported {len(results)} posts to {out_path}")
    return df

def get_account_insights(user_token: str, ig_id: str, metrics=None, period: str = "day", since=None, until=None, date_preset=None, filename=None, username: str | None = None):
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

    # Save into insights/ folder (use username if provided, else ig_id or provided filename)
    insights_dir = _get_insights_dir()
    if filename:
        out_filename = filename
    else:
        base = username if username else ig_id
        out_filename = f"account_insights_{base}.csv"
    out_path = insights_dir / (out_filename if out_filename.endswith(".csv") else Path(out_filename).with_suffix(".csv").name)

    # always save CSV
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"✅ Exported {len(df)} rows to {out_path}")
    return df
