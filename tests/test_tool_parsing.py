
import unittest
import logging
import sys
import os
import json

# Add parent directory to path to import perplexity_server
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from perplexity_server.bridge import ProtocolBridge as Bridge

# Mock logger
logging.basicConfig(level=logging.DEBUG)

class TestToolParsing(unittest.TestCase):
    def setUp(self):
        # Mock client and config
        self.bridge = Bridge()
        self.bridge.config = {"mode": "sonar", "model": "sonar-pro"}
        self.tools = [
            {
                "name": "Read",
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to file"}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "Bash",
                "description": "Run command",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command to run"}
                    },
                    "required": ["command"]
                }
            }
        ]

    def test_valid_tool_call(self):
        text = 'Here is the tool call:\nTOOL_CALL: {"name": "Read", "input": {"file_path": "/tmp/test.txt"}}'
        result = self.bridge._parse_tool_call(text, self.tools)
        self.assertIsNotNone(result)
        tool_call, start, end = result
        self.assertEqual(tool_call["name"], "Read")
        self.assertEqual(tool_call["input"]["file_path"], "/tmp/test.txt")

    def test_missing_required_param(self):
        # This should return None because file_path is required
        text = 'TOOL_CALL: {"name": "Read", "input": {}}'
        result = self.bridge._parse_tool_call(text, self.tools)
        self.assertIsNone(result)

    def test_flattened_param_recovery(self):
        # Test recovering flattened params
        text = 'TOOL_CALL: {"name": "Read", "file_path": "/tmp/flat.txt"}'
        result = self.bridge._parse_tool_call(text, self.tools)
        self.assertIsNotNone(result)
        tool_call, _, _ = result
        self.assertEqual(tool_call["name"], "Read")
        self.assertEqual(tool_call["input"]["file_path"], "/tmp/flat.txt")

    def test_hallucinated_param_name(self):
        # Test 'path' -> 'file_path'
        text = 'TOOL_CALL: {"name": "Read", "input": {"path": "/tmp/wrong_param.txt"}}'
        result = self.bridge._parse_tool_call(text, self.tools)
        self.assertIsNotNone(result)
        tool_call, _, _ = result
        self.assertEqual(tool_call["name"], "Read")
        self.assertEqual(tool_call["input"]["file_path"], "/tmp/wrong_param.txt")

    def test_bash_python_v(self):
         text = 'TOOL_CALL: {"name": "Bash", "input": {"command": "python -v", "description": "Check Python version"}}'
         result = self.bridge._parse_tool_call(text, self.tools)
         self.assertIsNotNone(result)
         tool_call, _, _ = result
         self.assertEqual(tool_call["name"], "Bash")
         self.assertEqual(tool_call["input"]["command"], "python -v")

if __name__ == '__main__':
    unittest.main()
