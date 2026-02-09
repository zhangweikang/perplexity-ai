import uvicorn
import json
import time
import os
from typing import List, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from .models import (
    OpenAIChatCompletionRequest,
    OpenAIResponsesRequest,
    ClaudeMessageRequest,
    GeminiGenerateContentRequest,
)
from .bridge import ProtocolBridge
from perplexity.exceptions import RateLimitError, AuthenticationError, ValidationError, PerplexityError
import sys

# Request logger storage / 请求日志存储
request_logs = []
MAX_LOGS = 100

# File logger / 文件日志
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "requests.log")

def log_to_file(content: str):
    """Append content to log file. / 将内容追加到日志文件。"""
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(content + "\n")

app = FastAPI(title="Perplexity API Bridge")
bridge = ProtocolBridge()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log request details / 记录请求详情
    path = request.url.path
    method = request.method
    start_time = time.time()
    
    # Skip logging for admin/static assets to avoid clutter
    is_admin = path.startswith("/admin") or path.startswith("/api") or path.startswith("/static")

    # Try to get body / 尝试获取正文
    body = await request.body()
    try:
        payload = json.loads(body) if body else None
    except:
        payload = body.decode() if body else None

    if not is_admin:
        print(f"\n--- [REQUEST] {method} {path} ---")
        if payload:
            print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        # Log to file for debugging / 记录到文件用于调试
        if path in ["/v1/chat/completions", "/v1/responses"]:
            log_to_file(f"\n{'='*60}")
            log_to_file(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] REQUEST: {method} {path}")
            log_to_file(f"{'='*60}")
            log_to_file(json.dumps(payload, indent=2, ensure_ascii=False) if payload else "No payload")
    
    # Process request / 处理请求
    request_id = f"{time.time()}-{id(request)}"
    response = await call_next(request)
    latency = round((time.time() - start_time) * 1000, 2)
    
    # Pre-add the log entry to ensure it exists for streaming updates
    # 预先添加日志条目，确保它存在以进行流式更新
    log_entry = None
    if not is_admin and (path in ["/v1/chat/completions", "/v1/messages", "/v1/responses"] or "/v1beta/models/" in path):
        # 协议判断
        if path == "/v1/responses" or "/v1/chat" in path:
            protocol = "OpenAI"
        elif "/v1/messages" in path:
            protocol = "Claude"
        else:
            protocol = "Gemini"
        
        # 提取模型名称 / Extract model name
        model_name = ""
        if isinstance(payload, dict):
            model_name = payload.get("model", "")
        
        log_entry = {
            "_id": request_id,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "method": method,
            "path": path,
            "protocol": protocol,
            "model": model_name,
            "input": json.dumps(payload, indent=2, ensure_ascii=False) if isinstance(payload, dict) else str(payload),
            "output": "[Streaming...]",
            "status": response.status_code,
            "latency": latency
        }
        request_logs.insert(0, log_entry)
        if len(request_logs) > MAX_LOGS:
            request_logs.pop()

    # Handle response body / 处理响应正文
    accumulated_content = ""
    if "text/event-stream" in response.headers.get("content-type", ""):
        original_iterator = response.body_iterator

        async def streaming_generator():
            nonlocal accumulated_content
            stream_start_time = time.time()
            async for chunk in original_iterator:
                chunk_str = chunk.decode(errors='ignore')
                accumulated_content += chunk_str
                
                # Update log entry in real-time if found
                if log_entry:
                    lines = chunk_str.split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            try:
                                data = json.loads(line[6:])
                                # Perplexity / OpenAI style (cumulative answer)
                                if 'answer' in data:
                                    log_entry["output"] = data['answer']
                                # OpenAI Delta style
                                elif 'choices' in data and data['choices']:
                                    delta = data['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        if log_entry["output"] == "[Streaming...]":
                                            log_entry["output"] = ""
                                        log_entry["output"] += delta['content']
                                # OpenAI Responses API style - delta
                                elif 'type' in data and data['type'] == 'response.output_text.delta':
                                    if log_entry["output"] == "[Streaming...]":
                                        log_entry["output"] = ""
                                    log_entry["output"] += data.get('delta', '')
                                # OpenAI Responses API style - done
                                elif 'type' in data and data['type'] == 'response.output_text.done':
                                    log_entry["output"] = data.get('text', log_entry.get("output", ""))
                                # Claude style
                                elif 'type' in data and data['type'] == 'content_block_delta':
                                    if log_entry["output"] == "[Streaming...]":
                                        log_entry["output"] = ""
                                    log_entry["output"] += data['delta'].get('text', '')
                            except:
                                pass
                yield chunk
            
            # 流式响应完成后更新耗时 / Update latency after streaming completes
            if log_entry:
                final_latency = round((time.time() - start_time) * 1000, 2)
                log_entry["latency"] = final_latency

        response.body_iterator = streaming_generator()
        response_content = "[Streaming Progress...]"
    else:
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        try:
            resp_json = json.loads(response_body)
            response_content = json.dumps(resp_json, indent=2, ensure_ascii=False)
        except:
            response_content = response_body.decode(errors='ignore')
            
        if log_entry:
            log_entry["output"] = response_content

        if not is_admin:
            print(f"Body: {response_content}")

        async def new_iterator():
            yield response_body
        response.body_iterator = new_iterator()

    if not is_admin:
        print(f"--- [RESPONSE] Status: {response.status_code} (Latency: {latency}ms) ---")
        print("-" * 40 + "\n")
        
        # Log response to file / 将响应记录到文件
        if path in ["/v1/chat/completions", "/v1/responses"] and log_entry:
            log_to_file(f"\n[RESPONSE] Status: {response.status_code} (Latency: {latency}ms)")
            log_to_file(log_entry.get("output", "[No output captured]"))
            log_to_file("-" * 60)
    return response

@app.get("/")
async def root():
    return {"message": "Perplexity API Bridge is running on port 8046"}

# --- OpenAI Endpoint ---

@app.post("/v1/chat/completions")
async def openai_chat_completions(request: OpenAIChatCompletionRequest):
    """OpenAI compatible chat completions endpoint. / OpenAI 兼容的聊天补全端点。"""
    try:
        result = await bridge.handle_openai(request)
        if isinstance(result, dict):
            return result
        else:
            return StreamingResponse(result, media_type="text/event-stream")
    except RateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PerplexityError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- OpenAI Responses API Endpoint ---

@app.post("/v1/responses")
async def openai_responses(request: OpenAIResponsesRequest):
    """OpenAI Responses API compatible endpoint. / OpenAI Responses API 兼容的端点。"""
    try:
        result = await bridge.handle_openai_responses(request)
        if isinstance(result, dict):
            return result
        else:
            return StreamingResponse(result, media_type="text/event-stream")
    except RateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PerplexityError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Claude Endpoint ---

@app.post("/v1/messages")
async def claude_messages(request: ClaudeMessageRequest):
    """Claude compatible messages endpoint. / Claude 兼容的消息端点。"""
    try:
        result = await bridge.handle_claude(request)
        if isinstance(result, dict):
            return result
        else:
            return StreamingResponse(result, media_type="text/event-stream")
    except RateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PerplexityError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Gemini Endpoint ---

@app.post("/v1beta/models/{model}:generateContent")
async def gemini_generate_content(model: str, request: GeminiGenerateContentRequest):
    """Gemini compatible generateContent endpoint. / Gemini 兼容的生成内容端点。"""
    try:
        # Note: Gemini streaming uses a different endpoint :streamGenerateContent
        result = await bridge.handle_gemini(model, request)
        return result
    except RateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PerplexityError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1beta/models/{model}:streamGenerateContent")
async def gemini_stream_generate_content(model: str, request: GeminiGenerateContentRequest):
    """Gemini compatible streamGenerateContent endpoint. / Gemini 兼容的流式生成内容端点。"""
    # Streaming for Gemini not fully implemented in bridge yet
    raise HTTPException(status_code=501, detail="Gemini streaming not yet implemented")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """Serve the admin management dashboard. / 提供管理后台。"""
    with open("perplexity_server/admin.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/logs")
async def get_logs():
    """Get request logs. / 获取请求日志。"""
    return request_logs

@app.get("/api/cookies")
async def get_cookies():
    """Get current bridge cookies. / 获取当前桥接器的 Cookie。"""
    return bridge.cookies

@app.post("/api/cookies")
async def update_cookies(cookies: Dict[str, str]):
    """Update bridge cookies. / 更新桥接器的 Cookie。"""
    bridge.update_cookies(cookies)
    return {"status": "success"}

@app.post("/api/capture-cookies")
async def capture_cookies():
    """
    Automatically capture cookies using Playwright. / 
    使用 Playwright 自动获取 Cookie。
    """
    try:
        cookies = await bridge.capture_perplexity_cookies()
        return {"status": "success", "cookies": cookies}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def start():
    """Start the server. / 启动服务器。"""
    print("\n" + "="*60)
    print("🚀 Perplexity API Bridge is starting!")
    print("="*60)
    print("⚠️  IMPORTANT: Pro and Reasoning modes require authentication.")
    print("Please ensure your cookies are configured in 'bridge.py' if you")
    print("want to use advanced models without reaching query limits.")
    print("Check README.md for instructions on how to obtain cookies.")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8046)

if __name__ == "__main__":
    start()
