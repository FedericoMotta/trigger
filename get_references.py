import os
import requests
from dotenv import load_dotenv
load_dotenv()   

import requests

def get_references(user_token, ig_id, username):
    # username = username.replace("@", "").strip()

    # fields = f"business_discovery.username({username}){{id}}"

    # url = f"https://graph.facebook.com/v24.0/{ig_id}"
    # params = {"fields": fields, "access_token": user_token}

    # response = requests.get(url, params=params).json()

    # if "error" in response:
    #     print("❌ API Error:", response["error"]["message"])
    #     return None

    # # Extract the profile ID
    # bd = response.get("business_discovery")
    # if not bd:
    #     print("No business_discovery data found.")
    #     return None

    # target_ig_id = bd.get("id")

    target_ig_id = "17841405480261603" 
    url = f"https://graph.instagram.com/v19.0/me/conversations?user_id={target_ig_id}"
    params = {"platform":"instagram",
        "access_token": os.getenv("IG_ACCESS_TOKEN"),
              }
    response = requests.get(url, params=params).json()
    print(response)