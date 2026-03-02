import requests
import json

BASE_URL = "http://localhost:8046"

def test_openai():
    print("\nTesting OpenAI endpoint (gpt-4)...")
    payload = {
        "model": "gpt-5.2-thinking",
        "messages": [{"role": "user", "content": "Hello, who are you?"}]
    }
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

def test_claude():
    print("\nTesting Claude endpoint...")
    payload = {
        "model": "claude-4.6-sonnet-thinking",
        "messages": [{"role": "user", "content": "How's the weather?"}],
        "max_tokens": 100
    }
    response = requests.post(f"{BASE_URL}/v1/messages", json=payload)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

def test_gemini():
    print("\nTesting Gemini endpoint...")
    payload = {
        "contents": [{"parts": [{"text": "Hello Gemini!"}]}]
    }
    # Perplexity maps gemini-pro to reasoning/gemini-pro
    response = requests.post(f"{BASE_URL}/v1beta/models/gemini-3.0-flash-thinking:generateContent", json=payload)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

def test_auto():
    print("\nTesting Perplexity Auto mode (Free)...")
    payload = {
        "model": "perplexity-auto",
        "messages": [{"role": "user", "content": "Tell me a short joke."}]
    }
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    try:
        # Test Free/Auto mode first
        #test_auto()
        
        # These might fail with 429 or 502 if Pro limit reached, but bridge is verified
        test_openai()
        test_claude()
        test_gemini()
    except Exception as e:
        print(f"Test Execution Error: {e}")
