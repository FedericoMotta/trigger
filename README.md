# Instagram Insights CLI

This tool lets you fetch Instagram Business insights, download media (including carousels), and analyze public profiles using the Facebook Graph API.

## How to Use

1. **Install dependencies**  
   Create a virtual environment and install requirements:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment**  
   Create a `.env` file in the project folder with:
   ```
   APP_ID=your_facebook_app_id
   APP_SECRET=your_facebook_app_secret
   REDIRECT_URI=https://google.com/
   ACCESS_TOKEN=your_access_token  # optional, can be set via menu
   ```

3. **Run the script**  
   Start the CLI:
   ```bash
   python main.py
   ```

4. **Follow the menu**  
   - **1:** Get USER access token (OAuth flow)
   - **2:** Select Instagram account (choose from your business accounts)
   - **3:** Get post insights (export as CSV or JSON)
   - **4:** Download media (owned, including carousels)
   - **5:** Get insights from any Instagram profile (business_discovery)
   - **6:** Download media from any public/business Instagram profile (not owned)
   - **0:** Exit

5. **Outputs**  
   - Insights are saved as CSV/JSON files in the project folder.
   - Downloaded media is saved in the `media/` folder.

## Notes

- For carousels, all images/videos are downloaded.
- You need a Facebook App with Instagram Graph API access and an Instagram Business Account.
- For transcription features, install ffmpeg and set `OPENAI_API_KEY` in `.env`.

## Troubleshooting

- If you see permission errors, re-authenticate and check your app's permissions.
- If carousels are missing children, ensure your account and token have the correct scopes.

---
