
import requests
import json
import os

URL = "http://127.0.0.1:8046/v1/chat/completions"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk-proj-123456" # Dummy key
}

def test_read_tool():
    # Create a dummy file to read
    with open("dummy_test_read.txt", "w") as f:
        f.write("This is a test file content.")

    abs_path = os.path.abspath("dummy_test_read.txt")
    
    # Payload asking to read the file
    data = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Please read the file at {abs_path} and tell me its content."}
        ],
        "stream": False,
        "tools": [
            {
                "name": "Read",
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "The absolute path to the file to read"}
                    },
                    "required": ["file_path"]
                }
            }
        ]
    }

    print(f"Sending request to read {abs_path}...")
    try:
        response = requests.post(URL, headers=HEADERS, json=data, timeout=60)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Response Response:")
            print(json.dumps(response.json(), indent=2))
            
            # Check if tool call is present
            content = response.json()['choices'][0]['message']['content']
            # ProtocolBridge might return content as a string, but if it parsed a tool call, 
            # it SHOULD return it in a structured way if we were using OpenAI format fully.
            # However, ProtocolBridge currently seems to put tool calls in 'content' textual description 
            # OR as tool_calls field?
            # Wait, `handle_openai` in bridge.py puts response in `content`. 
            # Does `bridge.py` support returning `tool_calls` in OpenAI format?
            # Let's check `handle_openai` implementation in bridge.py.
            
            # If `bridge.py` returns tool call as TEXT (which is what logs showed: "TOOL_CALL: ..."),
            # then we check for that string.
            if "TOOL_CALL:" in content:
                print("SUCCESS: Found TOOL_CALL in content.")
                if abs_path.replace("\\", "\\\\") in content or abs_path in content:
                     print("SUCCESS: File path found in tool call.")
                else:
                     print("WARNING: File path NOT found in tool call (check escaped chars).")
            else:
                print(f"FAILURE: No TOOL_CALL found in content.")
                print(f"Content received: {content}")
                
                # Fallback to Bash
                print("\nAttempting Bash fallback (cat)...")
                messages = data["messages"] # Get original messages
                messages.append({"role": "assistant", "content": content})
                # Use 'cat' with quoted path to handle spaces
                messages.append({"role": "user", "content": f"Fine, use the 'Bash' tool to run: cat \"{abs_path}\""})
                
                fallback_payload = data.copy()
                fallback_payload["messages"] = messages
                
                # Add Bash tool to the fallback payload
                # Use explicit list copy to avoid modifying original 'data' tools if referenced
                new_tools = list(data.get("tools", []))
                new_tools.append(
                    {
                        "name": "Bash",
                        "description": "Execute a bash command",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string", "description": "The bash command to execute"}
                            },
                            "required": ["command"]
                        }
                    }
                )
                fallback_payload["tools"] = new_tools

                print(f"Sending fallback request...")
                response = requests.post(URL, headers=HEADERS, json=fallback_payload, timeout=60)
                print(f"Fallback Status Code: {response.status_code}")
                if response.status_code == 200:
                    print("\nFallback Response:")
                    print(json.dumps(response.json(), indent=2))
                else:
                    print(f"Fallback Failed: {response.text}")
                
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_read_tool()
