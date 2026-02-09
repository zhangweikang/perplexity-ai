import json
import time
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, AsyncGenerator, Union
from .models import (
    OpenAIChatCompletionRequest,
    OpenAIResponsesRequest,
    ClaudeMessageRequest,
    GeminiGenerateContentRequest,
)
from uuid import uuid4
import perplexity_async
from perplexity.exceptions import RateLimitError, PerplexityError, AuthenticationError, ValidationError

# ========== 日志配置 / Logging Configuration ==========
# 日志文件路径
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE_LOG_FILE = os.path.join(LOG_DIR, "bridge_debug.log")

# 配置日志记录器 - 防止重复处理器
bridge_logger = logging.getLogger("bridge")
bridge_logger.setLevel(logging.DEBUG)

# 只有在没有处理器时才添加，防止重复
if not bridge_logger.handlers:
    # 文件处理器 - 记录到文件（使用 mode='a' 追加模式）
    file_handler = logging.FileHandler(BRIDGE_LOG_FILE, encoding="utf-8", mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    
    # 控制台处理器 - 同时输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    
    # 添加处理器
    bridge_logger.addHandler(file_handler)
    bridge_logger.addHandler(console_handler)
    
    # 禁止日志向上传播到root logger
    bridge_logger.propagate = False

# 立即刷新日志的包装函数
def flush_logs():
    """强制刷新所有日志处理器 / Force flush all log handlers."""
    for handler in bridge_logger.handlers:
        handler.flush()


def log_separator(title: str) -> None:
    """记录分隔符用于日志可读性 / Log separator for readability."""
    separator = "=" * 60
    bridge_logger.info(f"\n{separator}")
    bridge_logger.info(f"  {title}")
    bridge_logger.info(f"{separator}")
    flush_logs()


def log_request_params(protocol: str, request_data: dict) -> None:
    """记录请求参数 / Log request parameters."""
    log_separator(f"[{protocol}] 接收到请求 / Received Request")
    bridge_logger.info(f"原始请求参数 / Original Request:\n{json.dumps(request_data, indent=2, ensure_ascii=False)}")
    flush_logs()


def log_model_mapping(original_model: str, mapped_config: dict) -> None:
    """记录模型映射结果 / Log model mapping result."""
    bridge_logger.info(f"\n--- 模型映射 / Model Mapping ---")
    bridge_logger.info(f"原始模型 / Original Model: {original_model}")
    bridge_logger.info(f"映射结果 / Mapped Config: {json.dumps(mapped_config, indent=2, ensure_ascii=False)}")
    flush_logs()


def log_formatted_prompt(prompt: str) -> None:
    """记录格式化后的提示词 / Log formatted prompt."""
    bridge_logger.info(f"\n--- 格式化提示词 / Formatted Prompt ---")
    bridge_logger.info(f"Prompt:\n{prompt[:1000]}{'... [截断]' if len(prompt) > 1000 else ''}")
    flush_logs()


def log_perplexity_request(mode: str, model: str, stream: bool) -> None:
    """记录发送给 Perplexity 的请求 / Log request to Perplexity."""
    bridge_logger.info(f"\n--- 发送给 Perplexity / Sending to Perplexity ---")
    bridge_logger.info(f"Mode: {mode}, Model: {model}, Stream: {stream}")
    flush_logs()


def log_perplexity_response(response_data: Any, is_chunk: bool = False) -> None:
    """记录 Perplexity 原始响应 / Log raw Perplexity response."""
    if is_chunk:
        bridge_logger.debug(f"[Perplexity Chunk] {json.dumps(response_data, ensure_ascii=False)}")
    else:
        bridge_logger.info(f"\n--- Perplexity 原始响应 / Raw Response ---")
        bridge_logger.info(f"{json.dumps(response_data, indent=2, ensure_ascii=False)}")
    flush_logs()


def log_openai_response(response_data: dict, is_chunk: bool = False) -> None:
    """记录转换后的 OpenAI 格式响应 / Log converted OpenAI format response."""
    if is_chunk:
        bridge_logger.debug(f"[OpenAI Chunk] {json.dumps(response_data, ensure_ascii=False)}")
    else:
        log_separator("[OpenAI] 响应转换完成 / Response Converted")
        bridge_logger.info(f"OpenAI 格式响应 / OpenAI Format Response:\n{json.dumps(response_data, indent=2, ensure_ascii=False)}")
    flush_logs()


def log_claude_response(response_data: dict, is_chunk: bool = False) -> None:
    """记录转换后的 Claude 格式响应 / Log converted Claude format response."""
    if is_chunk:
        bridge_logger.debug(f"[Claude Chunk] {response_data}")
    else:
        log_separator("[Claude] 响应转换完成 / Response Converted")
        bridge_logger.info(f"Claude 格式响应 / Claude Format Response:\n{json.dumps(response_data, indent=2, ensure_ascii=False)}")
    flush_logs()

class ProtocolBridge:
    """
    Bridge between various API protocols and the Perplexity client. /
    各种 API 协议与 Perplexity 客户端之间的桥梁。
    """

    def __init__(self):
        self.client = None
        # ⚠️  Configuration: Add your cookies here / 在此处添加您的 Cookie
        # You can get these from your browser after logging in to perplexity.ai
        self.cookies = {
            'pplx.visitor-id': '3fd5142f-0de4-49c2-8e38-25e7f9caa17c',
            'pplx.search-mode': 'search',
            '__podscribe_perplexityai_referrer': '_',
            '__podscribe_perplexityai_landing_url': 'https://www.perplexity.ai/',
            'intercom-device-id-l2wyozh0': 'c0a89bbd-afcb-4960-ab98-f61b05a06cdc',
            '__stripe_mid': '8dd3af99-d6f0-4062-9c47-18dedacec965e797ae',
            'pplx.side-upsell-enterprise-dismissed': 'true',
            'pplx.search-models': '{%22search%22:%22claude2%22%2C%22research%22:%22pplx_alpha%22}',
            'IndrX2c1OFdjNG9oXzgxd1JocUVVWGFadkNMVEZaYlkzeGRCUlRlR1JldWhCX2Fub255bW91c1VzZXJJZCI%3D': 'IjYwMzU1ZGVjLWFkZDQtNDhjZS04N2E2LTllZmI5NzM2ZTlmNCI=',
            'segmented-control-popover-studio': '1',
            'sidebarHiddenHubs': '[%22SIDEBAR_FINANCE%22%2C%22SIDEBAR_SHOPPING%22%2C%22SIDEBAR_TRAVEL%22%2C%22SIDEBAR_ACADEMIC%22]',
            'pplx.personal-search-badge-seen': '{%22sidebar%22:true%2C%22settingsSidebar%22:false%2C%22personalize%22:false}',
            'ph_phc_TXdpocbGVeZVm5VJmAsHTMrCofBQu3e0kN8HGMNGTVW_posthog': '%7B%22distinct_id%22%3A%220197c895-93b1-70e1-bf9b-1ae66ca85d5b%22%2C%22%24sesid%22%3A%5B1751417530678%2C%220197c895-93b0-7535-89d8-64168839a40e%22%2C1751416935344%5D%7D',
            '__ps_fva': '1762407677889',
            '_fbp': 'fb.1.1762407678309.905207218777665437',
            '_ga_SH9PRBQG23': 'GS2.1.s1765444231$o1$g0$t1765444231$j60$l0$h0',
            '_ga': 'GA1.1.1168252117.1765444231',
            'gov-badge': '3',
            'sidebar-upgrade-badge': '2',
            '_rdt_uuid': '1762407677875.fee7782e-0104-4257-84f3-2f21b9c72cf3',
            '_gcl_au': '1.1.1251418162.1765444246',
            'g_state': '{"i_l":0,"i_ll":1770461021681,"i_e":{"enable_itp_optimization":0}}',
            'next-auth.csrf-token': '1eb3c379ba609e31cb32c04562a29289d971ac4e7319bd76e1a6a2f9a19f7f5d%7Cb1c7912e214a0d3404a67bc78a3715c3666399944ca60b1f441c54771c4051ca',
            'next-auth.callback-url': 'https%3A%2F%2Fwww.perplexity.ai%2Fapi%2Fauth%2Fsignin-callback%3Fredirect%3Dhttps%253A%252F%252Fwww.perplexity.ai%252F%253Flogin-source%253DoneTapHome',
            '__cflb': '02DiuDyvFMmK5p9jVbVnMNSKYZhUL9aGmzjVRNndciJyS',
            'cf_clearance': 'KrfkYTZisOBb4n0iFpXycLPpxUTWgo.K3QlJ9AxvMyw-1770615563-1.2.1.1-q6iRDLoIALTicR4y3MW2c1jZ.d8QwruIzYkD1o.eXILNyrPSSznOtzm6AE0pBeVcvDeyLByuzuGI7aLRisD2DOgU6E4i7RXJRYfHo.4Bs.gfOApRBGMLfogxaH2W8VHRzUwzsbp7zXFNZgL.qT0hE.V4kHrq76eqTy4m9iHbwB5ulWWEXWPd02zSUt4_4B0gxANygr2HMcDd30LW.ce_fXRBP8lvVnq1qFynlZrRJLk',
            '__Secure-next-auth.session-token': 'eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..Vkjc1h_kB5wjB0oJ.OniFpNHqEJxoH3owwbxn3IruUSmJkrVH1G3tKgTqF_Fv3TrQgJR06cYkO2W_prBpA21Ig3lS-uiQPS4AMzyu1fbAP_eHfFnZIXLpjjF_xCSLq-0QQt2W_S1NjjbXe_kBQ0C-lgNx7aIkeukBsJfJS-QXyEjeEMoOjx4OOzkj_AxvORxY3nkaOcO0LoLEjJK5IYiSJoOxFY6sOLu0DACjqPDOw--R28f8AXr-_kCC_xWvzKKJgVcZ8FqizPH-4WlNBkO3WQRrA4dW3Y_EjeEJq15yP5mwCdnG94XpARTLufL69j9RJKJDfcOEWmhEc-UfQqUvdHD0pSDDPYPN_Rkvh0UDW5IiteqRPpVRvW-GDIRF_Hk41IVMP0hnCFjSrljd7OkQ0Fot7zUVWiMbyM_5QRCfXEFwmAEQbSr4VsUw9GlI3kdET0g5.UZ1VyvIdDGjnjeeVBhSpMg',
            '__cf_bm': '4UTYRloMffDoZS8QLb3ksodYfzZKI9VNtVBfhmI7rZk-1770616173-1.0.1.1-kTv7Y0cj530pafqLvjV6yHDmr148yWSqmoWaXollayXsKD2jreCjcDnAVoa60x4kMP67SEQQykyg6H8GKdnd2ZaYwYUcrHVR.8ukzPNggBI',
            'pplx.metadata': '{%22qc%22:7%2C%22qcu%22:692%2C%22qcm%22:23%2C%22qcc%22:629%2C%22qcco%22:0%2C%22qccol%22:0%2C%22qcdr%22:0%2C%22qcs%22:0%2C%22qcd%22:0%2C%22hli%22:true%2C%22hcga%22:true%2C%22hcds%22:false%2C%22hso%22:true%2C%22hfo%22:true%2C%22hsco%22:false%2C%22hfco%22:false%2C%22hsma%22:false%2C%22hdc%22:true%2C%22hdttb%22:false%2C%22qcr%22:0%2C%22fqa%22:1770616192586%2C%22lqa%22:1770616192586}',
            '_dd_s': 'aid=9294629c-5cf2-4938-9d6c-62efa1815c12&rum=2&id=a0f1000f-d3c0-4060-8623-6403c1bc931d&created=1770615554715&expire=1770617954747&logs=0'
        }

    async def capture_perplexity_cookies(self) -> Dict[str, str]:
        """
        Automatically capture cookies by opening a headful browser. /
        通过打开有界面浏览器自动捕获 Cookie。
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("Playwright is not installed. Please install it with 'pip install playwright' and run 'playwright install'.")

        async with async_playwright() as p:
            # Launch headful browser / 启动有界面浏览器
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            print("🚀 Opening browser for cookie capture... / 正在打开浏览器以捕获 Cookie...")
            await page.goto("https://www.perplexity.ai/")
            
            # Informative message for the user in the browser / 在浏览器中给用户的信息提示
            await page.evaluate("""
                const div = document.createElement('div');
                div.style.position = 'fixed';
                div.style.top = '0';
                div.style.left = '0';
                div.style.width = '100%';
                div.style.background = '#007AFF';
                div.style.color = 'white';
                div.style.padding = '10px';
                div.style.textAlign = 'center';
                div.style.zIndex = '9999';
                div.innerHTML = '<b>API Bridge:</b> 请在此登录并确保你可以正常对话。完成后请保持 10 秒，脚本将自动获取 Cookie 并关闭。';
                document.body.appendChild(div);
            """)

            # Wait for meaningful cookies to appear or timeout after 60s
            # 等待有意义的 Cookie 出现或 60 秒后超时
            captured = {}
            for _ in range(60):
                await page.wait_for_timeout(1000)
                cookies = await context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                
                # Check for critical session cookie / 检查关键会话 Cookie
                if '__Secure-next-auth.session-token' in cookie_dict:
                    captured = cookie_dict
                    break
            
            await browser.close()
            
            if captured:
                self.update_cookies(captured)
                return captured
            else:
                raise Exception("Failed to capture cookies within timeout. / 在超时时间内未能捕获 Cookie。")

    def update_cookies(self, new_cookies: Dict[str, str]):
        """Update the client's cookies and re-initialize the client. / 更新客户端的 Cookie 并重新初始化客户端。"""
        self.cookies.update(new_cookies)
        self.client = None # Force re-initialization on next ensure_client() / 下一次 ensure_client() 时强制重新初始化

    async def ensure_client(self):
        """Ensure the Perplexity client is initialized. / 确保 Perplexity 客户端已初始化。"""
        if self.client is None:
            # Use cookies if provided, otherwise client runs in anonymous mode
            # 如果提供了 Cookie 则使用，否则客户端以匿名模式运行
            self.client = await perplexity_async.Client(cookies=self.cookies if any(self.cookies.values()) else {})

    def _map_model(self, model_name: str) -> Dict[str, Any]:
        """
        Map external model names to Perplexity modes and models. /
        将外部模型名称映射到 Perplexity 的模式和模型。
        """
        model_name = model_name.lower()
        
        # Default settings / 默认设置
        config = {
            "mode": "auto",
            "model": None,
        }

        if "thinking" in model_name or "reasoning" in model_name:
            config["mode"] = "reasoning"
            if "gpt-5" in model_name:
                config["model"] = "gpt-5.2-thinking"
            elif "claude-4.5" in model_name:
                config["model"] = "claude-4.5-sonnet-thinking"
            elif "gemini-3.0-flash" in model_name:
                config["model"] = "gemini-3.0-flash-thinking"
            elif "gemini-3.0-pro" in model_name:
                config["model"] = "gemini-3.0-pro"
            elif "grok-4.1" in model_name:
                config["model"] = "grok-4.1-reasoning"
            elif "kimi-k2.5" in model_name:
                config["model"] = "kimi-k2.5-thinking"
            else:
                config["model"] = None # Default reasoning
        elif "gpt-4" in model_name or "gpt-5" in model_name:
            config["mode"] = "pro"
            config["model"] = "gpt-5.2"
        elif "claude-4.6-opus" in model_name:
            config["mode"] = "pro"
            config["model"] = "claude-4.6-opus"
        elif "claude-3" in model_name or "claude-4" in model_name:
            config["mode"] = "pro"
            config["model"] = "claude-4.5-sonnet"
        elif "gemini-3.0-flash" in model_name:
            config["mode"] = "pro"
            config["model"] = "gemini-3.0-flash"
        elif "gemini" in model_name:
            config["mode"] = "pro"
            config["model"] = "gemini-3.0-pro"
        elif "grok-4.1" in model_name:
            config["mode"] = "pro"
            config["model"] = "grok-4.1"
        elif "kimi-k2.5" in model_name:
            config["mode"] = "pro"
            config["model"] = "kimi-k2.5"
        elif "sonar" in model_name:
            config["mode"] = "pro"
            config["model"] = "sonar"
        elif "perplexity-auto" in model_name or "auto" in model_name:
            config["mode"] = "auto"
            config["model"] = None
        
        return config

    def _format_openai_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Flatten OpenAI messages into a single prompt. / 将 OpenAI 消息展平为单个提示词。"""
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt += f"{role.capitalize()}: {content}\n\n"
        return prompt.strip()

    def _format_claude_prompt(self, request: ClaudeMessageRequest) -> str:
        """Flatten Claude messages and system prompt. / 将 Claude 消息和系统提示词展平。"""
        prompt = ""
        if request.system:
            prompt += f"System: {request.system}\n\n"
        
        for msg in request.messages:
            role = msg.role
            content = msg.content
            if isinstance(content, list):
                # Handle multi-modal content if needed / 如果需要，处理多模态内容
                text_content = " ".join([part.get("text", "") for part in content if part.get("type") == "text"])
                prompt += f"{role.capitalize()}: {text_content}\n\n"
            else:
                prompt += f"{role.capitalize()}: {content}\n\n"
        return prompt.strip()

    def _format_gemini_prompt(self, request: GeminiGenerateContentRequest) -> str:
        """Flatten Gemini contents into a single prompt. / 将 Gemini 内容展平为单个提示词。"""
        prompt = ""
        for content in request.contents:
            role = content.role or "user"
            parts_text = " ".join([part.text for part in content.parts if part.text])
            prompt += f"{role.capitalize()}: {parts_text}\n\n"
        return prompt.strip()

    # --- OpenAI Translation ---

    async def handle_openai(self, request: OpenAIChatCompletionRequest) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        await self.ensure_client()
        
        # 记录请求参数 / Log request parameters
        request_data = {
            "model": request.model,
            "messages": [m.dict() for m in request.messages],
            "stream": request.stream,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        }
        log_request_params("OpenAI", request_data)
        
        config = self._map_model(request.model)
        log_model_mapping(request.model, config)
        
        prompt = self._format_openai_prompt([m.dict() for m in request.messages])
        log_formatted_prompt(prompt)
        
        if request.stream:
            log_perplexity_request(config["mode"], config.get("model"), True)
            return self._stream_openai(request.model, prompt, config)
        
        log_perplexity_request(config["mode"], config.get("model"), False)
        resp = await self.client.search(prompt, mode=config["mode"], model=config["model"])
        log_perplexity_response(resp)
        
        openai_response = {
            "id": f"chatcmpl-{uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "system_fingerprint": "fp_perplexity_bridge",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": resp.get("answer", ""),
                },
                "logprobs": None,
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(prompt) // 4,
                "completion_tokens": len(resp.get("answer", "")) // 4,
                "total_tokens": (len(prompt) + len(resp.get("answer", ""))) // 4
            }
        }
        log_openai_response(openai_response)
        return openai_response

    async def _stream_openai(self, model: str, prompt: str, config: Dict[str, Any]) -> AsyncGenerator[str, None]:
        chat_id = f"chatcmpl-{int(time.time())}"
        created = int(time.time())
        
        bridge_logger.info(f"[OpenAI Stream] 开始流式响应 / Starting stream, chat_id={chat_id}")
        flush_logs()
        
        # Track sent text to calculate deltas / 跟踪已发送文本以计算增量
        last_sent_text = ""
        role_sent = False
        chunk_count = 0

        async for chunk in await self.client.search(prompt, mode=config["mode"], model=config["model"], stream=True):
            # 记录 Perplexity 原始流式响应块
            log_perplexity_response(chunk, is_chunk=True)
            
            if "answer" in chunk:
                full_answer = chunk['answer']
                delta_content = full_answer[len(last_sent_text):]
                
                if delta_content or not role_sent:
                    choice = {
                        'index': 0,
                        'delta': {},
                        'finish_reason': None
                    }
                    
                    if not role_sent:
                        choice['delta']['role'] = 'assistant'
                        role_sent = True
                    
                    if delta_content:
                        choice['delta']['content'] = delta_content
                        last_sent_text = full_answer

                    openai_chunk = {
                        'id': chat_id,
                        'object': 'chat.completion.chunk',
                        'created': created,
                        'model': model,
                        'system_fingerprint': 'fp_perplexity_bridge',
                        'choices': [choice]
                    }
                    chunk_count += 1
                    log_openai_response(openai_chunk, is_chunk=True)
                    
                    yield f"data: {json.dumps(openai_chunk)}\n\n"
        
        bridge_logger.info(f"[OpenAI Stream] 流式响应完成 / Stream completed, total_chunks={chunk_count}")
        bridge_logger.info(f"[OpenAI Stream] 完整响应内容 / Full response:\n{last_sent_text[:500]}{'...[截断]' if len(last_sent_text) > 500 else ''}")
        
        # Send final stop chunk / 发送最终停止块
        final_chunk = {
            'id': chat_id,
            'object': 'chat.completion.chunk',
            'created': created,
            'model': model,
            'choices': [{
                'index': 0,
                'delta': {},
                'finish_reason': 'stop'
            }]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    # --- OpenAI Responses API Translation ---

    def _format_responses_prompt(self, request: OpenAIResponsesRequest) -> str:
        """
        Format OpenAI Responses API input into a prompt. /
        将 OpenAI Responses API 输入格式化为提示词。
        """
        prompt = ""
        
        # Add instructions as system prompt if provided
        if request.instructions:
            prompt += f"System: {request.instructions}\n\n"
        
        # Handle input - can be string, list of messages, or list of dicts
        if request.input is None:
            return prompt.strip()
        
        if isinstance(request.input, str):
            prompt += f"User: {request.input}\n\n"
        elif isinstance(request.input, list):
            for item in request.input:
                if isinstance(item, dict):
                    role = item.get("role", "user")
                    content = item.get("content", "")
                    if isinstance(content, list):
                        # Handle content array (e.g., for multi-modal)
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "input_text":
                                text_parts.append(part.get("text", ""))
                            elif isinstance(part, dict) and part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                        content = " ".join(text_parts)
                    prompt += f"{role.capitalize()}: {content}\n\n"
                else:
                    # OpenAIResponsesInput object
                    role = getattr(item, "role", "user")
                    content = getattr(item, "content", "")
                    prompt += f"{role.capitalize()}: {content}\n\n"
        
        return prompt.strip()

    async def handle_openai_responses(self, request: OpenAIResponsesRequest) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        Handle OpenAI Responses API requests. /
        处理 OpenAI Responses API 请求。
        """
        await self.ensure_client()
        
        # 记录请求参数 / Log request parameters
        request_data = {
            "model": request.model,
            "input": request.input if isinstance(request.input, str) else str(request.input)[:500],
            "instructions": request.instructions,
            "stream": request.stream,
            "temperature": request.temperature,
            "max_output_tokens": request.max_output_tokens
        }
        log_request_params("OpenAI Responses API", request_data)
        
        config = self._map_model(request.model)
        log_model_mapping(request.model, config)
        
        prompt = self._format_responses_prompt(request)
        log_formatted_prompt(prompt)
        
        if request.stream:
            log_perplexity_request(config["mode"], config.get("model"), True)
            return self._stream_openai_responses(request.model, prompt, config)
        
        log_perplexity_request(config["mode"], config.get("model"), False)
        resp = await self.client.search(prompt, mode=config["mode"], model=config["model"])
        log_perplexity_response(resp)
        
        response_id = f"resp_{uuid4().hex[:12]}"
        output_text = resp.get("answer", "")
        
        # Build OpenAI Responses API format response
        openai_response = {
            "id": response_id,
            "object": "response",
            "created_at": int(time.time()),
            "status": "completed",
            "model": request.model,
            "output": [
                {
                    "type": "message",
                    "id": f"msg_{uuid4().hex[:8]}",
                    "status": "completed",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": output_text
                        }
                    ]
                }
            ],
            "usage": {
                "input_tokens": len(prompt) // 4,
                "output_tokens": len(output_text) // 4,
                "total_tokens": (len(prompt) + len(output_text)) // 4
            }
        }
        log_openai_response(openai_response)
        return openai_response

    async def _stream_openai_responses(self, model: str, prompt: str, config: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """
        Stream OpenAI Responses API format. /
        流式输出 OpenAI Responses API 格式。
        """
        response_id = f"resp_{uuid4().hex[:12]}"
        msg_id = f"msg_{uuid4().hex[:8]}"
        created = int(time.time())
        
        bridge_logger.info(f"[OpenAI Responses Stream] 开始流式响应 / Starting stream, response_id={response_id}")
        flush_logs()
        
        # Send initial response created event
        yield f"event: response.created\ndata: {json.dumps({'type': 'response.created', 'response': {'id': response_id, 'object': 'response', 'status': 'in_progress', 'model': model}})}\n\n"
        
        # Send output item created
        yield f"event: response.output_item.added\ndata: {json.dumps({'type': 'response.output_item.added', 'item': {'type': 'message', 'id': msg_id, 'role': 'assistant', 'status': 'in_progress'}})}\n\n"
        
        last_sent_text = ""
        chunk_count = 0
        
        async for chunk in await self.client.search(prompt, mode=config["mode"], model=config["model"], stream=True):
            log_perplexity_response(chunk, is_chunk=True)
            
            if "answer" in chunk:
                full_answer = chunk['answer']
                delta_content = full_answer[len(last_sent_text):]
                
                if delta_content:
                    chunk_count += 1
                    # Send content delta
                    delta_event = {
                        "type": "response.output_text.delta",
                        "item_id": msg_id,
                        "output_index": 0,
                        "content_index": 0,
                        "delta": delta_content
                    }
                    yield f"event: response.output_text.delta\ndata: {json.dumps(delta_event)}\n\n"
                    last_sent_text = full_answer
        
        bridge_logger.info(f"[OpenAI Responses Stream] 流式响应完成 / Stream completed, total_chunks={chunk_count}")
        flush_logs()
        
        # Send completion events
        yield f"event: response.output_text.done\ndata: {json.dumps({'type': 'response.output_text.done', 'item_id': msg_id, 'text': last_sent_text})}\n\n"
        yield f"event: response.output_item.done\ndata: {json.dumps({'type': 'response.output_item.done', 'item': {'type': 'message', 'id': msg_id, 'role': 'assistant', 'status': 'completed'}})}\n\n"
        yield f"event: response.completed\ndata: {json.dumps({'type': 'response.completed', 'response': {'id': response_id, 'status': 'completed'}})}\n\n"
        yield "event: done\ndata: [DONE]\n\n"

    # --- Claude Translation ---

    async def handle_claude(self, request: ClaudeMessageRequest) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        await self.ensure_client()
        
        config = self._map_model(request.model)
        prompt = self._format_claude_prompt(request)
        
        if request.stream:
            return self._stream_claude(request.model, prompt, config)
        
        resp = await self.client.search(prompt, mode=config["mode"], model=config["model"])
        
        return {
            "id": f"msg_{int(time.time())}",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": resp.get("answer", "")}],
            "model": request.model,
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": len(prompt) // 4,
                "output_tokens": len(resp.get("answer", "")) // 4
            }
        }

    async def _stream_claude(self, model: str, prompt: str, config: Dict[str, Any]) -> AsyncGenerator[str, None]:
        msg_id = f"msg_{int(time.time())}"
        input_tokens = len(prompt) // 4
        
        yield f"event: message_start\ndata: {json.dumps({
            'type': 'message_start',
            'message': {
                'id': msg_id, 
                'type': 'message', 
                'role': 'assistant', 
                'content': [], 
                'model': model,
                'usage': {'input_tokens': input_tokens, 'output_tokens': 0}
            }
        })}\n\n"
        
        yield f"event: content_block_start\ndata: {json.dumps({
            'type': 'content_block_start',
            'index': 0,
            'content_block': {'type': 'text', 'text': ''}
        })}\n\n"
        
        full_answer = ""
        last_sent_text = ""
        async for chunk in await self.client.search(prompt, mode=config["mode"], model=config["model"], stream=True):
            if "answer" in chunk:
                full_answer = chunk['answer']
                delta_content = full_answer[len(last_sent_text):]
                
                if delta_content:
                    yield f"event: content_block_delta\ndata: {json.dumps({
                        'type': 'content_block_delta',
                        'index': 0,
                        'delta': {'type': 'text_delta', 'text': delta_content}
                    })}\n\n"
                    last_sent_text = full_answer

        yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
        yield f"event: message_delta\ndata: {json.dumps({
            'type': 'message_delta',
            'delta': {'stop_reason': 'end_turn', 'stop_sequence': None},
            'usage': {'output_tokens': len(full_answer) // 4}
        })}\n\n"
        yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"

    # --- Gemini Translation ---

    async def handle_gemini(self, model: str, request: GeminiGenerateContentRequest) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        await self.ensure_client()
        
        config = self._map_model(model)
        prompt = self._format_gemini_prompt(request)
        
        # Gemini streaming usually uses a different endpoint, but we'll handle it here if possible.
        # For now, let's just implement the non-streaming one.
        
        resp = await self.client.search(prompt, mode=config["mode"], model=config["model"])
        
        return {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [{"text": resp.get("answer", "")}]
                },
                "finishReason": "STOP",
                "index": 0,
                "safetyRatings": [],
            }],
            "usageMetadata": {
                "promptTokenCount": len(prompt) // 4,
                "candidatesTokenCount": len(resp.get("answer", "")) // 4,
                "totalTokenCount": (len(prompt) + len(resp.get("answer", ""))) // 4
            }
        }
