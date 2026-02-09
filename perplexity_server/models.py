from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field

# --- OpenAI Models / OpenAI 模型 ---

class OpenAIMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class OpenAIChatCompletionRequest(BaseModel):
    model: str
    messages: List[OpenAIMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    max_tokens: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    user: Optional[str] = None

# --- OpenAI Responses API Models / OpenAI Responses API 模型 ---

class OpenAIResponsesInput(BaseModel):
    """Input content for Responses API / Responses API 的输入内容"""
    type: Optional[str] = "message"
    role: Optional[str] = "user"
    content: Optional[str] = None

class OpenAIResponsesRequest(BaseModel):
    """OpenAI Responses API request format / OpenAI Responses API 请求格式"""
    model: str
    input: Optional[Union[str, List[OpenAIResponsesInput], List[Dict[str, Any]]]] = None
    instructions: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    max_output_tokens: Optional[int] = None
    stream: Optional[bool] = False
    metadata: Optional[Dict[str, Any]] = None

# --- Claude (Anthropic) Models / Claude 模型 ---

class ClaudeMessage(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]

class ClaudeMessageRequest(BaseModel):
    model: str
    messages: List[ClaudeMessage]
    system: Optional[str] = None
    max_tokens: int
    metadata: Optional[Dict[str, Any]] = None
    stop_sequences: Optional[List[str]] = None
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None

# --- Gemini (Google) Models / Gemini 模型 ---

class GeminiPart(BaseModel):
    text: Optional[str] = None
    # Inline data, etc. omitted for simplicity / 简化起见省略了内联数据等

class GeminiContent(BaseModel):
    role: Optional[str] = "user"
    parts: List[GeminiPart]

class GeminiGenerationConfig(BaseModel):
    stopSequences: Optional[List[str]] = None
    candidateCount: Optional[int] = None
    maxOutputTokens: Optional[int] = None
    temperature: Optional[float] = None
    topP: Optional[float] = None
    topK: Optional[int] = None

class GeminiGenerateContentRequest(BaseModel):
    contents: List[GeminiContent]
    generationConfig: Optional[GeminiGenerationConfig] = None
    # safetySettings, etc. omitted / 省略安全设置等
