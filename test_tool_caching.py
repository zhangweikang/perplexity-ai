import requests
import json
import time
import sys

BASE_URL = "http://127.0.0.1:8046/v1/messages"

def test_cache():
    headers = {"x-api-key": "test-session-cache-verify"}
    
    # 1. Request with tools
    payload1 = {
        "model": "claude-3-sonnet",
        "messages": [{"role": "user", "content": "Hello, do you have tools?"}],
        "tools": [
            {
                "name": "test_tool_read",
                "description": "A test tool to read files", 
                "input_schema": {
                    "type": "object",
                    "properties": {"file_path": {"type": "string"}},
                    "required": ["file_path"]
                }
            }
        ],
        "max_tokens": 50,
        "stream": False
    }
    
    print("Sending request 1 (WITH tools)...")
    try:
        resp1 = requests.post(BASE_URL, json=payload1, headers=headers, timeout=30)
        print(f"Response 1: {resp1.status_code}")
        # print(resp1.json())
    except Exception as e:
        print(f"Error 1: {e}")

    time.sleep(2)

    # 2. Request WITHOUT tools
    payload2 = {
        "model": "claude-3-sonnet",
        "messages": [{"role": "user", "content": "Please use the test tool to read file.txt"}],
        # tools field is OMITTED
        "max_tokens": 50,
        "stream": False
    }
    print("\nSending request 2 (WITHOUT tools)...")
    try:
        resp2 = requests.post(BASE_URL, json=payload2, headers=headers, timeout=30)
        print(f"Response 2: {resp2.status_code}")
        # print(resp2.json())
    except Exception as e:
        print(f"Error 2: {e}")

if __name__ == "__main__":
    test_cache()
