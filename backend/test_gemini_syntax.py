import os
import json
import asyncio
from google import genai
from google.genai import types

def test_gemini():
    api_key = os.environ.get("GEMINI_API_KEY", "missing")
    if api_key == "missing":
         print("Missing GEMINI_API_KEY, cannot test")
         return
    
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents="Say 'OK'",
        )
        print("Response:", response.text)
    except Exception as e:
        print("Gemini error:", e)

if __name__ == "__main__":
    test_gemini()
