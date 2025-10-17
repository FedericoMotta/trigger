import whisper
from google import genai
import os 
from dotenv import load_dotenv
from google import genai
import json

instructions = open("/Users/fede/Documents/test/prompt.txt","r", encoding="utf-8").read()
load_dotenv()
model = whisper.load_model("base")
result = model.transcribe("media/test.mp4")
# Prepare the prompt for Gemini: include content data, transcript, and video file path as JSON

content_data = {
    "media_id": "18039892997612535",
    "media_type": "VIDEO",
    "media_url": "media/test.mp4",
    "transcript": result["text"],
    "caption":"",
    "timestamp":"2025-04-07T16:47:59+0000",
    "media_type":"VIDEO",
    "comments":53,
    "follows":0,
    "likes":1774,
    "navigation":0,
    "profile_activity":0,
    "profile_visits":0,
    "reach":257301,
    "replies":0,
    "saved":1259,
    "shares":1113,
    "views":1769}

gemini_prompt = {
    "instruction": instructions,
    "content": content_data
}

# Convert prompt to JSON string for Gemini
main_prompt = json.dumps(gemini_prompt, ensure_ascii=False, indent=2)

client = genai.Client(api_key=os.getenv("API_KEY"))
response = client.models.generate_content(
    model="gemini-2.5-flash", contents=main_prompt
)


print(response.text)