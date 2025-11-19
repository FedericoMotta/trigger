import os
import json
from google import genai
from google.genai.errors import ServerError
import time
from html_to_pdf import html_to_pdf
from get_outliers import get_outliers
import requests



def generate_in_depth_report(access_token, ig_id, username):
    # Paths to required files
    prompt_path = "in-depth_prompt.txt"
    framework_path = "behavioral_framework.txt"
    outlier_json_path = os.path.join(f"outlier_media/{username}/{username}_outlier_media_results.json")
    output_txt_path = os.path.join(f"outlier_media/{username}/{username}_in_depth_report.html")

    # Read prompt and framework
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_text = f.read()
    with open(framework_path, "r", encoding="utf-8") as f:
        framework_text = f.read()
    # Read outlier JSON
    with open(outlier_json_path, "r", encoding="utf-8") as f:
        outlier_json = json.load(f)
    outlier_json_str = json.dumps(outlier_json, indent=2, ensure_ascii=False)

    # Compose the full prompt
    full_prompt = (
        f"{prompt_text}\n\n"
        f"IMPORTANT: Return pure HTML code without any markdown wrappers (no ```html or ```). "
        f"Use absolute URLs or data URIs for images.\n\n"
        f"Behavioral Framework:\n{framework_text}\n\n"
        f"Outlier Data (JSON):\n{outlier_json_str}\n"
    )

    client = genai.Client()
    retries = 5
    raw_text = None
    for attempt in range(retries):
        try:
            print(f"🧠 Attempt {attempt + 1}/{retries} for Gemini...")
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[full_prompt],
            )
            print("🧩 Gemini raw response:", response)
            raw_text = response.text.strip()
            break
        except ServerError as e:
            if "503" in str(e):
                wait = 2 ** attempt
                print(f"⚠️ Gemini overloaded (503). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise e
    else:
        raise RuntimeError("❌ Gemini API failed after multiple attempts.")

    result_text = raw_text if raw_text else ""

    # Inject banner image at the top of the HTML
    banner_html = """
    <a href="https://triggersocial.io">
        <img src="file:///Users/fede/Documents/test/Banner.png" alt="Banner" style="max-width: 100px; width: 100%; height: auto;">
    </a>
    """
    
    # Insert banner after <body> tag or at the start if no body tag
    if '<body>' in result_text:
        result_text = result_text.replace('<body>', f'<body>\n{banner_html}')
    elif '<body' in result_text:  # Handle <body class="...">
        import re
        result_text = re.sub(r'(<body[^>]*>)', rf'\1\n{banner_html}', result_text)
    else:
        # No body tag, prepend banner
        result_text = banner_html + result_text

    # Export result as html
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write(result_text)
    
    print(f"✅ Generating pdf report...")

    pdf_output_path = f"outlier_media/{username}/{username}_in_depth_report.pdf"

    html_to_pdf(output_txt_path, pdf_output_path)
    
    print(f"✅ In-depth report exported to {output_txt_path}")



