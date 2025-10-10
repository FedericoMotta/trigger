import requests
from config import APP_ID, APP_SECRET

def select_instagram_account(user_token: str):
    """
    Returns selected IG ID (string) or None.
    """
    if not (APP_ID and APP_SECRET):
        print("APP_ID and APP_SECRET required for debug_token.")
        return None

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
        return None

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

    return accounts[sel - 1]["id"]

def extract_username_from_url(url: str):
    try:
        parts = url.strip("/").split("/")
        if "instagram.com" in parts:
            idx = parts.index("instagram.com")
            return parts[idx + 1]
        for i, part in enumerate(parts):
            if "instagram.com" in part and i + 1 < len(parts):
                return parts[i + 1]
        return parts[-1]
    except Exception:
        return None
