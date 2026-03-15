import requests
import json
import os

# Configuration
API_URL = "http://localhost:8000/api/process-inbox"
# Mock Token - the backend current only checks if a token exists
HEADERS = {
    "Authorization": "Bearer mock_token_for_testing"
}

# Mock PII data collected from "onboarding"
PII_DATA = {
    "names": ["דוד", "מירי", "David", "Miri"],
    "ids": ["123456789", "987654321"],
    "emails": ["david@gmail.com", "miri@gmail.com"],
    "debug": True  # This will save images to backend/debug_redaction and return them
}

def test_processing():
    print(f"Sending request to {API_URL}...")
    try:
        response = requests.post(API_URL, json=PII_DATA, headers=HEADERS)
        response.raise_for_status()
        
        result = response.json()
        print("\n--- Processing Results ---")
        print(f"Status: {result.get('status')}")
        print(f"Files Processed: {result.get('processed_count')}")
        
        for entry in result.get('results', []):
            print(f"\nFile: {entry['filename']}")
            if 'error' in entry:
                print(f"Error: {entry['error']}")
            else:
                data = entry['data']
                print(f"Owner: {data.get('owner_name')}")
                print(f"Total Accumulation: {data.get('total_accumulation')}")
                print(f"Products Found: {len(data.get('products', []))}")
                
                if 'preview_images' in entry:
                    print(f"PREVIEW: Received {len(entry['preview_images'])} redacted images in response.")
                    print(f"Check the folder: backend/debug_redaction for the PNG files.")
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the backend. Is it running on http://localhost:8000?")
    except Exception as e:
        print(f"An error occurred: {e}")
        if 'response' in locals() and response.text:
            print(f"Response content: {response.text}")

if __name__ == "__main__":
    test_processing()
