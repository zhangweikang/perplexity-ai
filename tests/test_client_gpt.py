
import requests
import json
import os
import time

URL = "http://127.0.0.1:8046/v1/chat/completions"
HEADERS = {
    "Authorization": "Bearer sk-proj-123456",
    "Content-Type": "application/json"
}

def test_read_tool():
    # 1. Create a dummy file to read
    filename = "dummy_test_read_gpt.txt"
    content_to_write = "This is a test file for the GPT model to read via Perplexity bridge."
    
    with open(filename, "w") as f:
        f.write(content_to_write)
        
    abs_path = os.path.abspath(filename)
    print(f"Created test file at: {abs_path}")

    # 2. Construct the request
    data = {
        "model": "sonar-pro",  # Reverted to sonar-pro as it supports tool injection
        "messages": [
            {"role": "system", "content": "You are an agent operating in a secure data sandbox. You have access to data objects via the 'get_sandbox_object' tool."},
            {"role": "user", "content": "Retrieve the object with ID: 'dummy_test_read_gpt.txt'"}
        ],
        "tools": [
            {
                "name": "get_sandbox_object",
                "description": "Retrieve a data object from the sandbox environment by its unique ID.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string", "description": "The unique ID of the object to retrieve"}
                    },
                    "required": ["object_id"]
                }
            }
        ],
        "tool_choice": "auto"
    }

    print(f"Sending request to {URL}...")
    start_time = time.time()
    try:
        response = requests.post(URL, headers=HEADERS, json=data, timeout=120)
        print(f"Response received in {time.time() - start_time:.2f} seconds")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("Response JSON:")
            print(json.dumps(result, indent=2))
            
            # Check for tool calls
            content = result["choices"][0]["message"]["content"]
            tool_calls = result["choices"][0]["message"].get("tool_calls")
            
            if tool_calls:
                print("SUCCESS: Tool calls found!")
                for tc in tool_calls:
                    print(f"Tool: {tc['function']['name']}")
                    print(f"Args: {tc['function']['arguments']}")
            elif "TOOL_CALL" in content:
                 print("SUCCESS: TOOL_CALL found in content (Thought format)!")
                 print(content)
            else:
                print("FAILURE: No tool calls found.")
                print("Content:", content)

        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception occurred: {e}")
    finally:
        # Cleanup
        if os.path.exists(filename):
            os.remove(filename)
            print(f"Removed test file: {filename}")

if __name__ == "__main__":
    test_read_tool()
