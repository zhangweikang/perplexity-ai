import uvicorn
import json
import time
import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from .models import (
    OpenAIResponsesRequest,
    ClaudeMessageRequest,
    GeminiGenerateContentRequest,
    OpenAIChatCompletionRequest,
)
from .bridge import ProtocolBridge
from perplexity.exceptions import RateLimitError, AuthenticationError, ValidationError, PerplexityError
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors."""
    error_msg = f"Validation Error for {request.method} {request.url.path}: {exc.errors()}"
    print(f"ERROR: {error_msg}")
    log_to_file(f"[VALIDATION ERROR] {error_msg}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

def _extract_session_id(request: Request) -> str:
    """
    Extract session ID from request headers. /
    从请求头中提取会话标识。
    优先查找包含 'api-key' 的头（如 x-api-key、api-key 等），
    其次检查 Authorization Bearer，最后回退到 x-session-id。
    """
    # 1. 查找任何包含 'api-key' 的请求头 / Find any header containing 'api-key'
    for key, value in request.headers.items():
        if "api-key" in key.lower() and value:
            return value
    
    # 2. 检查 Authorization Bearer / Check Authorization Bearer
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    
    # 3. 回退到 x-session-id / Fallback to x-session-id
    return request.headers.get("x-session-id", "")

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
        
        # Log to file for debugging / 记录到文件用于调试
        log_to_file(f"\n{'='*60}")
        log_to_file(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] REQUEST: {method} {path}")
        log_to_file(f"{'='*60}")
        log_to_file("Headers:")
        for k, v in request.headers.items():
            log_to_file(f"  {k}: {v}")
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
        original_model = ""
        if isinstance(payload, dict):
            original_model = payload.get("model", "")
        # Gemini: 从 URL 路径提取模型 / Extract model from URL path for Gemini
        if not original_model and "/v1beta/models/" in path:
            model_part = path.split("/v1beta/models/")[-1]
            original_model = model_part.split(":")[0] if ":" in model_part else model_part
        
        # 获取完整模型映射 / Get full model mapping (alias + Perplexity mapping)
        mapped_model = ""
        display_model = original_model
        if original_model:
            try:
                mapped = bridge._map_model(original_model)
                mapped_model = mapped.get("model", "")
                if mapped_model and mapped_model.lower() != original_model.lower():
                    display_model = f"{original_model} → {mapped_model}"
            except:
                pass
        
        log_entry = {
            "_id": request_id,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "method": method,
            "path": path,
            "protocol": protocol,
            "model": display_model,
            "original_model": original_model,
            "mapped_model": mapped_model or original_model,
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
                                # Gemini style
                                elif 'candidates' in data and data['candidates']:
                                    parts = data['candidates'][0].get('content', {}).get('parts', [])
                                    for part in parts:
                                        if 'text' in part and part['text']:
                                            if log_entry["output"] == "[Streaming...]":
                                                log_entry["output"] = ""
                                            log_entry["output"] += part['text']
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

@app.get("/v1/models")
async def list_models():
    """OpenAI compatible models listing. / OpenAI 兼容的模型列表端点。"""
    base_models = [
        "default", "turbo", "pro", "reasoning",
        "gpt-4o", "gpt-4o-mini", "gpt-4.5-preview",
        "claude-3.5-sonnet", "claude-3.5-haiku",
        "gemini-2.0-flash", "gemini-2.0-flash-thinking",
        "sonar", "sonar-pro", "sonar-reasoning",
    ]
    # 合并别名模型 / Merge alias models
    aliases = bridge.get_model_aliases()
    all_models = list(set(base_models + list(aliases.keys()) + list(aliases.values())))
    all_models.sort()
    
    return {
        "object": "list",
        "data": [
            {
                "id": m,
                "object": "model",
                "created": 0,
                "owned_by": "perplexity-bridge",
            }
            for m in all_models
        ],
    }

# --- OpenAI Endpoint ---

@app.post("/v1/chat/completions")
async def openai_chat_completions(request: OpenAIChatCompletionRequest, raw_request: Request):
    """OpenAI compatible chat completions endpoint. / OpenAI 兼容的聊天补全端点。"""
    session_id = _extract_session_id(raw_request)
    try:
        result = await bridge.handle_openai(request, session_id=session_id)
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
async def openai_responses(request: OpenAIResponsesRequest, raw_request: Request):
    """OpenAI Responses API compatible endpoint. / OpenAI Responses API 兼容的端点。"""
    session_id = _extract_session_id(raw_request)
    try:
        result = await bridge.handle_openai_responses(request, session_id=session_id)
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
async def claude_messages(request: ClaudeMessageRequest, raw_request: Request):
    """Claude compatible messages endpoint. / Claude 兼容的消息端点。"""
    session_id = _extract_session_id(raw_request)
    try:
        result = await bridge.handle_claude(request, session_id=session_id)
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

@app.post("/v1/messages/count_tokens")
async def count_tokens(request: Request):
    """
    Dummy format for token counting to satisfy Claude clients.
    由于 Perplexity 没有提供 token 计算接口，这里进行简单的估算 (1 token ≈ 4 字符)
    以避免客户端报错。
    """
    try:
        body = await request.json()
        messages = body.get("messages", [])
        system = body.get("system", "")
        
        # Simple estimation: 4 chars = 1 token
        text_len = len(str(system))
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                text_len += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        text_len += len(part.get("text", ""))
        
        token_count = max(1, text_len // 4)
        return {"input_tokens": token_count}
    except Exception as e:
        print(f"Token count error: {e}")
        return {"input_tokens": 0}

# --- Gemini Endpoint ---

@app.post("/v1beta/models/{model}:generateContent")
async def gemini_generate_content(model: str, request: GeminiGenerateContentRequest, raw_request: Request):
    """Gemini compatible generateContent endpoint. / Gemini 兼容的生成内容端点。"""
    session_id = _extract_session_id(raw_request)
    try:
        # Note: Gemini streaming uses a different endpoint :streamGenerateContent
        result = await bridge.handle_gemini(model, request, session_id=session_id)
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
async def gemini_stream_generate_content(model: str, request: GeminiGenerateContentRequest, raw_request: Request):
    """Gemini compatible streamGenerateContent endpoint. / Gemini 兼容的流式生成内容端点。"""
    session_id = _extract_session_id(raw_request)
    try:
        result = await bridge.handle_gemini_stream(model, request, session_id=session_id)
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

@app.get("/api/sessions")
async def get_sessions():
    """Get active sessions. / 获取活跃会话列表。"""
    sessions = []
    for sid, data in bridge.sessions.items():
        sessions.append({
            "session_id": sid,
            "backend_uuid": data.get("backend_uuid", ""),
            "attachments_count": len(data.get("attachments", [])),
            "slug": data.get("slug", ""),
        })
    return sessions

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session. / 删除指定会话。"""
    if session_id in bridge.sessions:
        del bridge.sessions[session_id]
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Session not found")

@app.delete("/api/sessions")
async def clear_sessions():
    """Clear all sessions. / 清除所有会话。"""
    bridge.sessions.clear()
    return {"status": "success", "cleared": True}

@app.post("/api/threads")
async def list_threads(request: Request):
    """Fetch Perplexity thread history. / 获取 Perplexity 历史会话。"""
    body = await request.json()
    limit = body.get("limit", 20)
    offset = body.get("offset", 0)
    search_term = body.get("search_term", "")
    result = await bridge.list_threads(limit=limit, offset=offset, search_term=search_term)
    return result

@app.post("/api/sessions/bind")
async def bind_session(request: Request):
    """Bind a thread slug to a session_id. / 将线程 slug 绑定到 session_id。"""
    body = await request.json()
    session_id = body.get("session_id")
    slug = body.get("slug")
    backend_uuid = body.get("backend_uuid", "")
    if not session_id or not slug:
        raise HTTPException(status_code=400, detail="session_id and slug are required")
    bridge.bind_session(session_id, slug, backend_uuid)
    return {"status": "success", "session_id": session_id, "slug": slug}

@app.get("/api/threads/{slug:path}")
async def get_thread_detail(slug: str):
    """Get thread details by slug. / 通过 slug 获取对话详情。"""
    result = await bridge.get_thread_detail(slug)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    if not result:
        raise HTTPException(status_code=404, detail="Thread not found")
    return result

@app.post("/api/threads/delete")
async def delete_threads_endpoint(request: Request):
    """Delete threads by UUIDs. / 通过 UUID 列表删除对话。"""
    body = await request.json()
    uuids = body.get("uuids", [])
    if not uuids:
        raise HTTPException(status_code=400, detail="uuids list is required")
    result = await bridge.delete_threads(uuids)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

# --- Model Alias Config Endpoints ---

@app.get("/api/model-aliases")
async def get_model_aliases():
    """Get current model alias mappings. / 获取当前模型别名配置。"""
    return bridge.get_model_aliases()

@app.post("/api/model-aliases")
async def update_model_aliases(request: Request):
    """Update model alias mappings. / 更新模型别名配置。"""
    body = await request.json()
    updated = bridge.update_model_aliases(body)
    return {"status": "success", "aliases": updated}

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
