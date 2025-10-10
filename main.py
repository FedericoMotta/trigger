import config
from oauth import oauth_flow
from accounts import select_instagram_account, extract_username_from_url
from insights import get_post_insights, get_account_insights
from downloads import download_last_n_media, download_media_from_profile_business_discovery
from business_discovery import get_insights_for_profile_business_discovery

def main_menu():
    global config
    while True:
        print("\nChoose an option:")
        print("1. Get USER access token")
        print("2. Select Instagram account")
        print("3. Get post insights")
        print("4. Download media (owned)")
        print("5. Get insights from Instagram profile link (business_discovery)")
        print("6. Download media from a given Instagram profile (not owned)")
        print("0. Exit")

        choice = input("Enter 0,1,2,3,4,5,6: ").strip()

        if choice == "1":
            token = oauth_flow()
            if token:
                config.ACCESS_TOKEN = token
                print("Stored USER token (in config).")

        elif choice == "2":
            if not config.ACCESS_TOKEN:
                print("No USER token. Run option 1 first.")
            else:
                selected = select_instagram_account(config.ACCESS_TOKEN)
                if selected:
                    config.IG_ID = selected
                    print(f"Selected IG ID set to {config.IG_ID}")

        elif choice == "3":
            if not config.ACCESS_TOKEN or not config.IG_ID:
                print("You need to get a token and select an account first.")
            else:
                try:
                    n = int(input("How many recent posts do you want insights for? "))
                    export_format = input("Export as CSV or JSON? (csv/json): ").strip().lower()
                    if export_format not in ("csv", "json"):
                        export_format = "csv"
                    get_post_insights(config.ACCESS_TOKEN, config.IG_ID, filename="instagram_insights.csv", n=n, export_format=export_format)
                except Exception as e:
                    print(f"Invalid input: {e}")

        elif choice == "4":
            if not config.ACCESS_TOKEN or not config.IG_ID:
                print("You need to get a token and select an account first.")
            else:
                try:
                    n = int(input("How many recent media do you want to download? "))
                    download_last_n_media(config.ACCESS_TOKEN, config.IG_ID, n=n, folder="media")
                except Exception as e:
                    print(f"Invalid input: {e}")

        elif choice == "5":
            if not config.ACCESS_TOKEN or not config.IG_ID:
                print("You need to get a token and select an account first.")
            else:
                try:
                    url = input("Enter Instagram profile URL: ").strip()
                    n = int(input("How many recent posts do you want insights for? "))
                    export_format = input("Export as CSV or JSON? (csv/json): ").strip().lower()
                    rows = get_insights_for_profile_business_discovery(config.ACCESS_TOKEN, config.IG_ID, extract_username_from_url(url), n=n, export_format=export_format)
                    if rows:
                        import pandas as pd
                        df = pd.DataFrame(rows)
                        fname = (extract_username_from_url(url) or "profile") + ("_insights.json" if export_format=="json" else "_insights.csv")
                        if export_format == "json":
                            df.to_json(fname, orient="records", force_ascii=False, indent=2)
                        else:
                            df.to_csv(fname, index=False, encoding="utf-8-sig")
                        print(f"Exported to {fname}")
                except Exception as e:
                    print(f"Invalid input: {e}")

        elif choice == "6":
            if not config.ACCESS_TOKEN or not config.IG_ID:
                print("You need to get a token and select an account first.")
            else:
                try:
                    url = input("Enter Instagram profile URL: ").strip()
                    n = int(input("How many recent media do you want to download? "))
                    download_media_from_profile_business_discovery(config.ACCESS_TOKEN, config.IG_ID, url, n=n, folder="media")
                except Exception as e:
                    print(f"Invalid input: {e}")

        elif choice == "0":
            print("Bye!")
            break

        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main_menu()
 