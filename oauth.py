import sys
import urllib.parse
import webbrowser
import requests
import json
from config import APP_ID, APP_SECRET, REDIRECT_URI

def _print_json(title: str, obj):
    try:
        print(title + ":")
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    except Exception:
        print(title, obj)

def oauth_flow() -> str:
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
