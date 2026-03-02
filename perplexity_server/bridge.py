import json
import time
import logging
import os
import re
from datetime import datetime
from typing import List, Dict, Any, AsyncGenerator, Union, Optional, Tuple
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

    # 会话存储上限 / Maximum number of sessions to cache
    MAX_SESSIONS = 100

    # 默认模型别名 / Default model aliases
    DEFAULT_MODEL_ALIASES = {
        "gemini-3": "gemini-3.1-pro",
        "gemini-3-flash": "gemini-3.1-flash",
        "gpt-5": "gpt-5.2-thinking",
        "gpt-4": "gpt-5.2",
        "claude-4": "claude-4.6-sonnet-thinking",
        "claude-3": "claude-4.6-sonnet",
        "grok-4": "grok-4.1",
        "kimi-k2": "kimi-k2.5",
    }

    # 模型别名配置文件路径 / Model alias config file path
    ALIAS_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_aliases.json")

    def __init__(self):
        self.client = None
        # 会话存储：session_id -> {"backend_uuid": ..., "attachments": [...]} / Session store for follow_up
        self.sessions: Dict[str, dict] = {}
        # 加载模型别名配置 / Load model alias config
        self.model_aliases = self._load_model_aliases()
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
            from perplexity_async import Client
            self.client = await Client(cookies=self.cookies)
            bridge_logger.info("[Init] Perplexity client initialized / Perplexity 客户端已初始化")

    def _get_follow_up(self, session_id: str = None) -> dict:
        """
        Get follow_up data for an existing session. /
        获取会话的 follow_up 数据以支持追问。
        """
        if session_id and session_id in self.sessions:
            follow_up = self.sessions[session_id]
            bridge_logger.info(f"[Session] 使用已有会话 / Reusing session: {session_id}, backend_uuid={follow_up.get('backend_uuid')}")
            flush_logs()
            return follow_up
        return None

    def _save_session(self, session_id: str, response_data: dict):
        """
        Save session data from a Perplexity response for future follow-up. /
        从 Perplexity 响应中保存会话数据，供后续追问使用。
        """
        if not session_id:
            return
        backend_uuid = response_data.get("backend_uuid")
        if backend_uuid:
            # 保留已有的 slug 映射 / Preserve existing slug mapping
            existing = self.sessions.get(session_id, {})
            self.sessions[session_id] = {
                "backend_uuid": backend_uuid,
                "attachments": response_data.get("attachments", []),
                "slug": existing.get("slug", response_data.get("slug", "")),
            }
            # 限制会话存储数量 / Limit session store size
            if len(self.sessions) > self.MAX_SESSIONS:
                oldest_key = next(iter(self.sessions))
                del self.sessions[oldest_key]
            bridge_logger.info(f"[Session] 已保存会话 / Saved session: {session_id}, backend_uuid={backend_uuid}")
            flush_logs()

    async def list_threads(self, limit: int = 20, offset: int = 0, search_term: str = "") -> dict:
        """
        Fetch historical conversation threads from Perplexity API. /
        从 Perplexity API 获取历史对话列表。委托给 client.get_threads()。
        """
        await self.ensure_client()
        try:
            result = await self.client.get_threads(limit=limit, offset=offset, search_term=search_term)
            # 统一返回格式 / Normalize response format
            if isinstance(result, list):
                result = {"threads": result}
            threads = result.get("threads", [])
            bridge_logger.info(f"[Threads] 获取历史会话列表 / Fetched threads: offset={offset}, count={len(threads)}")
            flush_logs()
            return result
        except Exception as e:
            bridge_logger.error(f"[Threads] 获取历史会话失败 / Failed to fetch threads: {e}")
            flush_logs()
            return {"threads": []}

    def bind_session(self, session_id: str, slug: str, backend_uuid: str = ""):
        """
        Bind a thread slug to a session_id. /
        将历史会话的 slug 绑定到 session_id。
        """
        existing = self.sessions.get(session_id, {})
        self.sessions[session_id] = {
            "backend_uuid": existing.get("backend_uuid", backend_uuid),
            "attachments": existing.get("attachments", []),
            "slug": slug,
        }
        bridge_logger.info(f"[Session] 绑定会话 / Bound session: {session_id} -> slug={slug}")
        flush_logs()

    async def get_thread_detail(self, slug: str) -> dict:
        """
        Get thread details by slug. /
        通过 slug 获取对话详情。
        """
        await self.ensure_client()
        try:
            result = await self.client.get_thread_details_by_slug(slug)
            bridge_logger.info(f"[Threads] 获取对话详情 / Fetched thread detail: slug={slug}")
            flush_logs()
            return result
        except Exception as e:
            bridge_logger.error(f"[Threads] 获取对话详情失败 / Failed to fetch thread detail: {e}")
            flush_logs()
            return {"error": str(e)}

    async def delete_threads(self, uuids: list) -> dict:
        """
        Delete threads by UUIDs. /
        通过 UUID 列表删除对话。
        """
        await self.ensure_client()
        try:
            result = await self.client.delete_threads(uuids)
            bridge_logger.info(f"[Threads] 删除对话 / Deleted threads: count={len(uuids)}")
            flush_logs()
            return result
        except Exception as e:
            bridge_logger.error(f"[Threads] 删除对话失败 / Failed to delete threads: {e}")
            flush_logs()
            return {"error": str(e)}

    def _load_model_aliases(self) -> Dict[str, str]:
        """
        Load model aliases from config file, create with defaults if not exists. /
        从配置文件加载模型别名，不存在则使用默认值创建。
        """
        if os.path.exists(self.ALIAS_CONFIG_FILE):
            try:
                with open(self.ALIAS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    aliases = json.load(f)
                bridge_logger.info(f"[ModelAlias] 已加载 {len(aliases)} 个模型别名 / Loaded {len(aliases)} model aliases")
                flush_logs()
                return aliases
            except Exception as e:
                bridge_logger.error(f"[ModelAlias] 加载配置失败，使用默认值 / Failed to load config, using defaults: {e}")
                flush_logs()
        
        # 使用默认值并保存 / Use defaults and save
        self._save_model_aliases(self.DEFAULT_MODEL_ALIASES)
        return dict(self.DEFAULT_MODEL_ALIASES)

    def _save_model_aliases(self, aliases: Dict[str, str]) -> None:
        """Save model aliases to config file. / 将模型别名保存到配置文件。"""
        try:
            with open(self.ALIAS_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(aliases, f, indent=2, ensure_ascii=False)
            bridge_logger.info(f"[ModelAlias] 已保存 {len(aliases)} 个模型别名 / Saved {len(aliases)} model aliases")
            flush_logs()
        except Exception as e:
            bridge_logger.error(f"[ModelAlias] 保存配置失败 / Failed to save config: {e}")
            flush_logs()

    def update_model_aliases(self, aliases: Dict[str, str]) -> Dict[str, str]:
        """
        Update model aliases and save to file. / 更新模型别名并保存到文件。
        Returns the updated aliases.
        """
        self.model_aliases = aliases
        self._save_model_aliases(aliases)
        return self.model_aliases

    def get_model_aliases(self) -> Dict[str, str]:
        """Get current model aliases. / 获取当前模型别名。"""
        return self.model_aliases

    def _resolve_model_alias(self, model_name: str) -> str:
        """
        Resolve model alias to real model name. /
        将模型别名解析为实际模型名称。
        采用最长前缀匹配优先策略。
        """
        original = model_name
        model_lower = model_name.lower()
        
        # 按别名长度降序排序，优先匹配更精确的前缀 / Sort by length desc for longest prefix match first
        sorted_aliases = sorted(self.model_aliases.items(), key=lambda x: len(x[0]), reverse=True)
        
        for alias, target in sorted_aliases:
            if model_lower.startswith(alias.lower()):
                bridge_logger.info(f"[ModelAlias] 前缀匹配: '{original}' (prefix: '{alias}') -> '{target}'")
                flush_logs()
                return target
        
        return model_name

    def _map_model(self, model_name: str) -> Dict[str, Any]:
        """
        Map external model names to Perplexity modes and models. /
        将外部模型名称映射到 Perplexity 的模式和模型。
        """
        # 先进行别名解析 / Resolve alias first
        model_name = self._resolve_model_alias(model_name)
        model_name = model_name.lower()
        
        # 默认使用 reasoning 模式 / Default to reasoning mode
        config = {
            "mode": "reasoning",
            "model": None,
        }

        # 精确模式判断优先 / Explicit mode keywords first
        if "perplexity-auto" in model_name or model_name == "auto":
            config["mode"] = "auto"
            config["model"] = None
        elif "sonar" in model_name:
            config["mode"] = "pro"
            config["model"] = "sonar"
        # GPT 系列 / GPT series
        elif "gpt-5" in model_name:
            if "thinking" in model_name:
                config["mode"] = "reasoning"
            else:
                config["mode"] = "reasoning"
            config["model"] = "gpt-5.2-thinking"
        elif "gpt-4" in model_name:
            config["mode"] = "reasoning"
            config["model"] = "gpt-5.2-thinking"
        # Claude 系列 / Claude series
        elif "claude-4.6-opus" in model_name:
            config["mode"] = "reasoning"
            config["model"] = "claude-4.6-opus"
        elif "claude" in model_name:
            if "thinking" in model_name:
                config["model"] = "claude-4.6-sonnet-thinking"
            else:
                config["model"] = "claude-4.6-sonnet-thinking"
            config["mode"] = "reasoning"
        # Gemini 系列 / Gemini series
        elif "gemini-3.0-flash" in model_name or "gemini-3-flash" in model_name:
            config["mode"] = "reasoning"
            if "thinking" in model_name:
                config["model"] = "gemini-3.0-flash-thinking"
            else:
                config["model"] = "gemini-3.0-flash-thinking"
        elif "gemini" in model_name:
            config["mode"] = "reasoning"
            config["model"] = "gemini-3.1-pro"
        # Grok 系列 / Grok series
        elif "grok" in model_name:
            config["mode"] = "reasoning"
            config["model"] = "grok-4.1-reasoning"
        # Kimi 系列 / Kimi series
        elif "kimi" in model_name:
            config["mode"] = "reasoning"
            config["model"] = "kimi-k2.5-thinking"
        
        return config

    def _format_openai_prompt(self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]] = None) -> str:
        """Flatten OpenAI messages into a single prompt. / 将 OpenAI 消息展平为单个提示词。"""
        prompt = ""
    
        # Force system instruction
        force_system = (
            "You are an intelligent agent with access to external tools. "
            "You MUST use the provided tools to fulfill requests. "
            "If a tool is provided to fetch data, use it."
        )
        
        # Format tools if present
        tools_prompt = ""
        if tools:
            tools_prompt = self._format_tools_prompt(tools)
            force_system += tools_prompt
        
        has_system = any(m.get("role") == "system" for m in messages)
        if not has_system:
            prompt += f"System: {force_system}\n\n"

        # Find last user message index
        last_user_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                last_user_idx = i
                break
                
        prompt_hint = "\n\n(System Note: The user has provided custom tools for this session. You MUST use these tools to fulfill requests when applicable. Do not simulate tool outputs.)"

        for i, msg in enumerate(messages):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # 处理多部分内容数组 / Handle multi-part content array
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, dict) and part.get("type") == "input_text":
                        text_parts.append(part.get("text", ""))
                content = "\n".join(text_parts)
                
            if role == "system":
                content = f"{force_system}\n{content}"
                
            if i == last_user_idx and role == "user":
                bridge_logger.debug(f"[Prompt Format] Appending hint to last user message at index {i}")
                content += prompt_hint
                
            prompt += f"{role.capitalize()}: {content}\n\n"
        return prompt.strip()

    def _format_claude_prompt(self, request: ClaudeMessageRequest) -> str:
        """Flatten Claude messages and system prompt. / 将 Claude 消息和系统提示词展平。"""
        prompt = ""
        if request.system:
            system_content = request.system
            if isinstance(system_content, list):
                # Handle system prompt as list of blocks
                text_parts = []
                for part in system_content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                system_content = "\n".join(text_parts)
            
            prompt += f"System: You are an expert software engineer with access to the local filesystem. You MUST use the provided tools to read, write, and edit files as requested. Do not refuse to access local files. \n{system_content}\n\n"
        else:
            prompt += "System: You are an expert software engineer with access to the local filesystem. You MUST use the provided tools to read, write, and edit files as requested. Do not refuse to access local files.\n\n"
        
        for msg in request.messages:
            role = msg.role
            content = msg.content
            
            message_parts = []
            
            if isinstance(content, list):
                for part in content:
                    part_type = part.get("type")
                    if part_type == "text":
                        message_parts.append(part.get("text", ""))
                    elif part_type == "tool_use":
                        # Format past tool use mechanism
                        tool_name = part.get("name")
                        tool_input = part.get("input", {})
                        # Reconstruct the tool call string so Perplexity knows what it did
                        tool_call_json = json.dumps({"name": tool_name, "input": tool_input}, ensure_ascii=False)
                        message_parts.append(f"TOOL_CALL: {tool_call_json}")
                    elif part_type == "tool_result":
                        # Format tool result
                        # tool_use_id = part.get("tool_use_id")
                        result_content = part.get("content", "")
                        # Handle list content in tool_result (e.g. image + text) - simplistic handling for now
                        if isinstance(result_content, list):
                             text_segments = [p.get("text", "") for p in result_content if p.get("type") == "text"]
                             result_content = " ".join(text_segments)
                        
                        message_parts.append(f"[Tool Result]: {result_content}")
            else:
                message_parts.append(str(content))
                
            full_content = "\n".join(message_parts)
            prompt += f"{role.capitalize()}: {full_content}\n\n"
            
        # Add tools definition / 添加工具定义
        if request.tools:
            # Loop detection: count consecutive tool errors in history
            # 循环检测：统计历史中连续的工具错误
            consecutive_errors = 0
            for msg in reversed(request.messages):
                # messages are Pydantic objects with .content attribute, NOT dicts
                # 消息是 Pydantic 对象，使用属性访问而非 dict.get()
                role = getattr(msg, 'role', '') if not isinstance(msg, dict) else msg.get('role', '')
                content = getattr(msg, 'content', '') if not isinstance(msg, dict) else msg.get('content', '')
                
                # Skip assistant messages - errors alternate: user(error) → assistant(retry) → user(error)
                # 跳过 assistant 消息，错误模式是交替的
                if role == 'assistant':
                    continue
                
                if isinstance(content, list):
                    has_error = any(
                        (isinstance(p, dict) and p.get("type") == "tool_result" and (p.get("is_error") or "tool_use_error" in str(p.get("content", ""))))
                        for p in content
                    )
                    if has_error:
                        consecutive_errors += 1
                    else:
                        break
                elif isinstance(content, str) and "tool_use_error" in content:
                    consecutive_errors += 1
                else:
                    break
            
            bridge_logger.info(f"[Claude Prompt] Loop detection: found {consecutive_errors} consecutive tool errors in history")
            
            if consecutive_errors >= 3:
                bridge_logger.warning(f"[Claude Prompt] Detected {consecutive_errors} consecutive tool errors! Injecting recovery hint.")
                prompt += "\n\n**IMPORTANT: You have failed to use tools correctly multiple times in a row. "
                prompt += "STOP trying to use tools. Instead, respond with a plain text explanation of what you want to do. "
                prompt += "Do NOT output any TOOL_CALL. Just describe your intended action in natural language.**\n\n"
            else:
                bridge_logger.info(f"[Claude Prompt] Found {len(request.tools)} tools.")
                bridge_logger.debug(f"[Claude Prompt] Tools raw: {json.dumps(request.tools, ensure_ascii=False)}")
                tools_prompt = self._format_tools_prompt(request.tools)
                bridge_logger.debug(f"[Claude Prompt] Tools prompt segment:\n{tools_prompt}")
                prompt += tools_prompt
        else:
            bridge_logger.info("[Claude Prompt] No tools found in request.")
            
        bridge_logger.info(f"[Claude Prompt] Final prompt length: {len(prompt)}")
        bridge_logger.debug(f"[Claude Prompt] Final content:\n{prompt}")
            
        return prompt.strip()

    def _format_gemini_prompt(self, request: GeminiGenerateContentRequest) -> str:
        """Flatten Gemini contents into a single prompt. / 将 Gemini 内容展平为单个提示词。"""
        prompt = ""
        for content in request.contents:
            role = content.role or "user"
            parts_text = " ".join([part.text for part in content.parts if part.text])
            prompt += f"{role.capitalize()}: {parts_text}\n\n"
        return prompt.strip()

    def _format_tools_prompt(self, tools: List[Dict[str, Any]]) -> str:
        """Format tools into a prompt string. / 将工具列表格式化为提示词字符串。"""
        if not tools:
            return ""
        
        prompt = "\n\n## Tools Available\n"
        prompt += "When you need to use a tool, you MUST respond with EXACTLY this format (valid JSON):\n"
        prompt += 'TOOL_CALL: {"name": "ToolName", "input": {"param1": "value1", "param2": "value2"}}\n\n'
        prompt += "**CRITICAL RULES:**\n"
        prompt += "- The `input` object MUST contain ALL required parameters. Never leave input empty ({}).\n"
        prompt += "- Use the EXACT tool name as listed below (case-sensitive).\n"
        prompt += "- All parameter names and string values must be in double quotes (valid JSON).\n"
        prompt += '- For file operations (Read, Edit, Write), ALWAYS provide the full absolute `file_path`.\n'
        prompt += '- Example: TOOL_CALL: {"name": "Read", "input": {"file_path": "/absolute/path/to/file.txt"}}\n'
        prompt += '- Tools starting with "mcp__" are available specialized tools. Use them if they match your needs.\n'
        prompt += '- Do NOT run interactive commands like `python` (without args), `python -v`, or `bash` without a script. These will hang or fail.\n'
        prompt += '- To check versions, use `python --version`. to run code, use `python -c "..."` or write to a file and run it.\n\n'
        
        for tool in tools:
            # Handle OpenAI format and Claude format
            if "function" in tool:
                t_def = tool["function"]
                name = t_def.get("name", "")
                desc = t_def.get("description", "")
                schema = t_def.get("parameters", {})
            else:
                name = tool.get("name", "")
                desc = tool.get("description", "")
                schema = tool.get("input_schema", {})
            
            # Extract required params and properties
            required = schema.get("required", [])
            properties = schema.get("properties", {})
            
            # Build concise param list instead of full JSON schema
            param_parts = []
            for p_name, p_info in properties.items():
                p_type = p_info.get("type", "string")
                p_desc = p_info.get("description", "")
                req_marker = " [REQUIRED]" if p_name in required else ""
                # Truncate long descriptions
                if len(p_desc) > 80:
                    p_desc = p_desc[:77] + "..."
                param_parts.append(f"    - {p_name} ({p_type}){req_marker}: {p_desc}")
            
            prompt += f"### {name}\n"
            if desc:
                # Truncate long descriptions
                if len(desc) > 150:
                    desc = desc[:147] + "..."
                prompt += f"{desc}\n"
            if param_parts:
                prompt += "Parameters:\n"
                prompt += "\n".join(param_parts) + "\n"
            else:
                prompt += "Parameters: none\n"
            prompt += "\n"
            
        return prompt

    def _parse_tool_call(self, text: str, tools: List[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], int, int]]:
        """
        Parse tool call from text response. / 从文本响应中解析工具调用。
        Returns: (tool_call_dict, start_index, end_index) or None
        """
        # Note: tools might be None if request didn't include them, but we still try to parse standard format
        # 注意：如果请求未包含工具，tools 可能为 None，但我们仍尝试解析标准格式
        
        bridge_logger.debug(f"[Tool Parser] Parsing text (len={len(text)}), tools_available={bool(tools)}")
        if len(text) > 200:
             bridge_logger.debug(f"[Tool Parser] Text preview: {text[:200]}...")
        else:
             bridge_logger.debug(f"[Tool Parser] Text content: {text}")
            
        # 1. Try to match standard JSON format / 尝试匹配标准 JSON 格式
        # Use simple string search + json.raw_decode to handle nested braces correctly
        tool_call_marker = "TOOL_CALL:"
        start_idx = text.find(tool_call_marker)
        if start_idx != -1:
            # Find the first '{' after TOOL_CALL:
            json_start = text.find("{", start_idx)
            if json_start != -1:
                try:
                    bridge_logger.debug(f"[Tool Parser] Attempting JSON extraction at index {json_start}")
                    # raw_decode parses one valid JSON object and returns it along with the end index
                    tool_call, parsed_len = json.JSONDecoder().raw_decode(text[json_start:])
                    bridge_logger.debug(f"[Tool Parser] Successfully decoded JSON: {json.dumps(tool_call, ensure_ascii=False)}")
                
                    name = tool_call.get("name")
                    if not name:
                        bridge_logger.warning("[Tool Parser] JSON found but no 'name' field.")
                        # Skip tool call if no name
                        return None
                         
                    # Handle flattened arguments (per user report)
                    # 处理扁平化参数 (如 {"name": "Read", "path": "..."} 而非 {"name": "Read", "input": {"path": "..."}})
                    if "input" in tool_call:
                        input_args = tool_call["input"]
                        # Handle case where input is empty but params are at top level
                        # 处理 input 为空但参数在顶层的情况
                        if not input_args and len(tool_call) > 2:
                            input_args = {k: v for k, v in tool_call.items() if k not in ("name", "input")}
                            bridge_logger.info(f"[Tool Parser] Recovered flattened params from top level: {list(input_args.keys())}")
                    else:
                        input_args = {k: v for k, v in tool_call.items() if k != "name"}

                    # Tool Name Fuzzy Matching / 工具名称模糊匹配
                    # Fix hallucinations like 'read_file' -> 'Read', 'list_files' -> 'LS', etc.
                    matched_tool = None
                    if tools:
                        # 1. Exact match / 精确匹配
                        for t in tools:
                            if t.get("name") == name:
                                matched_tool = t
                                break
                        
                        # 2. Case-insensitive match / 忽略大小写匹配
                        if not matched_tool:
                            name_lower = name.lower()
                            for t in tools:
                                if t.get("name", "").lower() == name_lower:
                                    matched_tool = t
                                    bridge_logger.info(f"[Tool Parser] Case-insensitive match: '{name}' -> '{t['name']}'")
                                    name = t["name"]
                                    break
                        
                        # 3. Normalized match (strip underscores, compare) / 标准化匹配
                        # e.g. 'read_file' -> 'readfile', 'Read' -> 'read' -> 'read'
                        if not matched_tool:
                            norm_name = name.lower().replace("_", "").replace("-", "")
                            for t in tools:
                                t_norm = t.get("name", "").lower().replace("_", "").replace("-", "")
                                if t_norm == norm_name:
                                    matched_tool = t
                                    bridge_logger.info(f"[Tool Parser] Normalized match: '{name}' -> '{t['name']}'")
                                    name = t["name"]
                                    break
                        
                        # 4. Partial/contains match / 部分匹配
                        # e.g. 'read_file' contains 'read', tool 'Read' normalized is 'read'
                        if not matched_tool:
                            for t in tools:
                                t_norm = t.get("name", "").lower().replace("_", "")
                                if t_norm in norm_name or norm_name in t_norm:
                                    matched_tool = t
                                    bridge_logger.info(f"[Tool Parser] Partial match: '{name}' -> '{t['name']}'")
                                    name = t["name"]
                                    break
                        
                        if not matched_tool:
                            bridge_logger.warning(f"[Tool Parser] Tool '{name}' not found in {len(tools)} available tools. Returning as-is.")
                    
                    # Parameter Correction Logic / 参数纠正逻辑
                    if matched_tool:
                        props = matched_tool.get("input_schema", {}).get("properties", {})
                        required = matched_tool.get("input_schema", {}).get("required", [])
                        
                        # Fix 'path' -> 'file_path' hallucination
                        if "file_path" in props and "path" in input_args and "file_path" not in input_args:
                            bridge_logger.info(f"[Tool Parser] Correcting param 'path' -> 'file_path' for tool {name}")
                            input_args["file_path"] = input_args.pop("path")
                        
                        # Fix 'filepath' -> 'file_path' hallucination
                        if "file_path" in props and "filepath" in input_args and "file_path" not in input_args:
                            bridge_logger.info(f"[Tool Parser] Correcting param 'filepath' -> 'file_path' for tool {name}")
                            input_args["file_path"] = input_args.pop("filepath")
                        
                        # Generic: try to match missing required params by normalized names
                        # 通用: 尝试通过标准化名称匹配缺失的必需参数
                        for req_param in required:
                            if req_param not in input_args:
                                req_norm = req_param.lower().replace("_", "")
                                for arg_key in list(input_args.keys()):
                                    if arg_key.lower().replace("_", "") == req_norm:
                                        bridge_logger.info(f"[Tool Parser] Correcting param '{arg_key}' -> '{req_param}' for tool {name}")
                                        input_args[req_param] = input_args.pop(arg_key)
                                        break
                    
                    bridge_logger.info(f"[Tool Parser] Final tool call: name={name}, params={list(input_args.keys())}")
                    
                    # Required parameter validation / 必需参数验证
                    # If required params are missing after all corrections, reject the tool call
                    if matched_tool:
                        required = matched_tool.get("input_schema", {}).get("required", [])
                        missing = [r for r in required if r not in input_args]
                        if missing:
                            bridge_logger.warning(f"[Tool Parser] REJECTED tool '{name}': missing required params {missing}. input={input_args}")
                            bridge_logger.warning(f"[Tool Parser] Returning None to prevent broken tool_use response")
                            return None
                    
                    final_tool_call = {
                        "name": name,
                        "input": input_args
                    }
                    
                    # End index is absolute end of JSON
                    end_idx = json_start + parsed_len
                    return final_tool_call, start_idx, end_idx

                except Exception as e:
                    bridge_logger.error(f"[Tool Parser] JSON parse error: {e}")
                    pass
                
        # 2. Try to match Chinese pattern / 尝试匹配中文模式 "准备开始调用 xxx 工具"
        # Only if tools are available for validation
        if tools:
            cn_match = re.search(r'准备开始调用\s*(\S+)\s*工具', text)
            if cn_match:
                tool_name = cn_match.group(1)
                bridge_logger.debug(f"[Tool Parser] Found Chinese pattern for tool: {tool_name}")
                
                # Find the tool definition to check if it matches / 查找工具定义以检查是否匹配
                for tool in tools:
                    t_name = tool.get("function", {}).get("name") if "function" in tool else tool.get("name")
                    if t_name == tool_name:
                        # Try to extract JSON from the rest of the text if possible
                        start_idx = cn_match.start()
                        end_idx = cn_match.end()
                        
                        input_match = re.search(r'\{.*\}', text, re.DOTALL)
                        input_data = {}
                        if input_match:
                            try:
                                input_data = json.loads(input_match.group(0))
                                end_idx = max(end_idx, input_match.end())
                            except:
                                pass
                                
                        bridge_logger.info(f"[Tool Parser] Parsed Chinese tool call: name={tool_name}, input={input_data}")
                        return {"name": tool_name, "input": input_data}, start_idx, end_idx
        
        return None

    # --- OpenAI Translation ---

    async def handle_openai(self, request: OpenAIChatCompletionRequest, session_id: str = None) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        await self.ensure_client()
        follow_up = self._get_follow_up(session_id)
        
        # 记录请求参数 / Log request parameters
        try:
             request_data = {
                 "model": request.model,
                 "messages": [m.dict() for m in request.messages],
                 "stream": request.stream,
                 "max_tokens": request.max_tokens,
                 "tools_count": len(request.tools) if request.tools else 0
             }
             log_request_params("OpenAI", request_data)
        except Exception as e:
             bridge_logger.error(f"Failed to log request params: {e}")
        
        config = self._map_model(request.model)
        log_model_mapping(request.model, config)
        
        # Pass tools to prompt formatter
        request_tools = request.tools
        prompt = self._format_openai_prompt([m.dict() for m in request.messages], tools=request_tools)
        log_formatted_prompt(prompt)
        
        if request.stream:
            log_perplexity_request(config["mode"], config.get("model"), True)
            return self._stream_openai(request.model, prompt, config, session_id=session_id, follow_up=follow_up)
        
        log_perplexity_request(config["mode"], config.get("model"), False)
        resp = await self.client.search(prompt, mode=config["mode"], model=config["model"], follow_up=follow_up)
        log_perplexity_response(resp)
        self._save_session(session_id, resp)
        
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

    async def _stream_openai(self, model: str, prompt: str, config: Dict[str, Any], session_id: str = None, follow_up: dict = None) -> AsyncGenerator[str, None]:
        chat_id = f"chatcmpl-{int(time.time())}"
        created = int(time.time())
        
        bridge_logger.info(f"[OpenAI Stream] 开始流式响应 / Starting stream, chat_id={chat_id}")
        flush_logs()
        
        # Track sent text to calculate deltas / 跟踪已发送文本以计算增量
        last_sent_text = ""
        role_sent = False
        chunk_count = 0
        last_chunk = None

        async for chunk in await self.client.search(prompt, mode=config["mode"], model=config["model"], stream=True, follow_up=follow_up):
            last_chunk = chunk
            # 记录 Perplexity 原始流式响应块
            log_perplexity_response(chunk, is_chunk=True)
            
            # 思考/搜索阶段发送 keep-alive 防止客户端超时
            # Send keep-alive comment during thinking/searching phase
            if "answer" not in chunk:
                yield ": keepalive\n\n"
                continue
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
        
        # 保存会话信息用于追问 / Save session for follow-up
        if last_chunk:
            self._save_session(session_id, last_chunk)
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

    async def handle_openai_responses(self, request: OpenAIResponsesRequest, session_id: str = None) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        Handle OpenAI Responses API requests. /
        处理 OpenAI Responses API 请求。
        """
        await self.ensure_client()
        follow_up = self._get_follow_up(session_id)
        
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
            return self._stream_openai_responses(request.model, prompt, config, session_id=session_id, follow_up=follow_up)
        
        log_perplexity_request(config["mode"], config.get("model"), False)
        resp = await self.client.search(prompt, mode=config["mode"], model=config["model"], follow_up=follow_up)
        log_perplexity_response(resp)
        self._save_session(session_id, resp)
        
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

    async def _stream_openai_responses(self, model: str, prompt: str, config: Dict[str, Any], session_id: str = None, follow_up: dict = None) -> AsyncGenerator[str, None]:
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
        last_chunk = None
        
        async for chunk in await self.client.search(prompt, mode=config["mode"], model=config["model"], stream=True, follow_up=follow_up):
            last_chunk = chunk
            log_perplexity_response(chunk, is_chunk=True)
            
            # 思考/搜索阶段发送 keep-alive / Send keep-alive during thinking phase
            if "answer" not in chunk:
                yield ": keepalive\n\n"
                continue

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
        
        # 保存会话信息用于追问 / Save session for follow-up
        if last_chunk:
            self._save_session(session_id, last_chunk)
        bridge_logger.info(f"[OpenAI Responses Stream] 流式响应完成 / Stream completed, total_chunks={chunk_count}")
        flush_logs()
        
        # Send completion events
        yield f"event: response.output_text.done\ndata: {json.dumps({'type': 'response.output_text.done', 'item_id': msg_id, 'text': last_sent_text})}\n\n"
        yield f"event: response.output_item.done\ndata: {json.dumps({'type': 'response.output_item.done', 'item': {'type': 'message', 'id': msg_id, 'role': 'assistant', 'status': 'completed'}})}\n\n"
        yield f"event: response.completed\ndata: {json.dumps({'type': 'response.completed', 'response': {'id': response_id, 'status': 'completed'}})}\n\n"
        yield "event: done\ndata: [DONE]\n\n"

    # --- Claude Translation ---

    async def handle_claude(self, request: ClaudeMessageRequest, session_id: str = None) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        await self.ensure_client()

        # Session defaults
        if not session_id:
             session_id = f"claude-{uuid4().hex[:8]}"

        # Cache tools in session / 在会话中缓存工具
        # If request has tools, update cache. If not, use cached tools.
        if request.tools:
            if session_id not in self.sessions:
                self.sessions[session_id] = {"attachments": []}
            self.sessions[session_id]["tools"] = request.tools
            bridge_logger.debug(f"[Session] Updated cached tools for {session_id} (count={len(request.tools)})")
        elif session_id in self.sessions and "tools" in self.sessions[session_id]:
            request.tools = self.sessions[session_id]["tools"]
            bridge_logger.debug(f"[Session] Using cached tools for {session_id} (count={len(request.tools)})")
        
        # 打印获取到的 tools 列表
        if request.tools:
            tool_names = [t.get('name', 'unknown') for t in request.tools]
            bridge_logger.info(f"[Claude] 获取到 {len(request.tools)} 个工具: {tool_names}")
        else:
            bridge_logger.info("[Claude] 未获取到任何工具")
        
        follow_up = self._get_follow_up(session_id)
        
        # 记录请求参数
        try:
             request_data = {
                 "model": request.model,
                 "messages": [m.dict() if hasattr(m, "dict") else str(m) for m in request.messages],
                 "stream": request.stream,
                 "max_tokens": request.max_tokens,
                 "tools_count": len(request.tools) if request.tools else 0
             }
             log_request_params("Claude", request_data)
        except Exception as e:
             bridge_logger.error(f"Failed to log request params: {e}")
        
        config = self._map_model(request.model)
        prompt = self._format_claude_prompt(request)
        
        if request.stream:
            return self._stream_claude(request.model, prompt, config, session_id=session_id, follow_up=follow_up, tools=request.tools)
        
        resp = await self.client.search(prompt, mode=config["mode"], model=config["model"], follow_up=follow_up)
        self._save_session(session_id, resp)
        
        answer_text = resp.get("answer", "")
        
        # 打印 Perplexity 原始返回数据
        bridge_logger.info(f"[Claude] ===== Perplexity 原始返回 =====")
        bridge_logger.info(f"[Claude] 原始返回长度: {len(answer_text)} 字符")
        if len(answer_text) > 500:
            bridge_logger.info(f"[Claude] 原始返回预览: {answer_text[:500]}...")
        else:
            bridge_logger.info(f"[Claude] 原始返回全文: {answer_text}")
        
        content_value = [{"type": "text", "text": answer_text}]
        stop_reason = "end_turn"
        
        # Check for tool call / 检查工具调用
        tool_data = self._parse_tool_call(answer_text, request.tools)
        if tool_data:
            tool_call, tc_start, tc_end = tool_data
            content_value = []
            
            # Preserve preceding text (thinking / context) as separate text block
            # 保留工具调用前的文本（思考/上下文）作为独立文本块
            pre_text = answer_text[:tc_start].strip()
            if pre_text:
                content_value.append({"type": "text", "text": pre_text})
            
            content_value.append({
                "type": "tool_use",
                "id": f"toolu_{uuid4().hex[:15]}",
                "name": tool_call["name"],
                "input": tool_call["input"]
            })
            stop_reason = "tool_use"
        
        final_response = {
            "id": f"msg_{int(time.time())}",
            "type": "message",
            "role": "assistant",
            "content": content_value,
            "model": request.model,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": len(prompt) // 4,
                "output_tokens": len(answer_text) // 4
            }
        }
        
        # 打印处理后的返回数据
        bridge_logger.info(f"[Claude] ===== 处理后的返回数据 =====")
        bridge_logger.info(f"[Claude] stop_reason: {stop_reason}")
        bridge_logger.info(f"[Claude] content blocks: {len(content_value)}")
        for i, block in enumerate(content_value):
            if block['type'] == 'text':
                text_preview = block['text'][:200] + '...' if len(block['text']) > 200 else block['text']
                bridge_logger.info(f"[Claude]   [{i}] type=text, text={text_preview}")
            elif block['type'] == 'tool_use':
                bridge_logger.info(f"[Claude]   [{i}] type=tool_use, name={block['name']}, input={json.dumps(block['input'], ensure_ascii=False)[:300]}")
        flush_logs()
        
        return final_response

    async def _stream_claude(self, model: str, prompt: str, config: Dict[str, Any], session_id: str = None, follow_up: dict = None, tools: Optional[List[Dict[str, Any]]] = None) -> AsyncGenerator[str, None]:
        msg_id = f"msg_{int(time.time())}"
        input_tokens = len(prompt) // 4
        
        try:
            # Buffer full response to check for tool calls / 缓冲完整响应以检查工具调用
            full_answer = ""
            last_chunk = None
            
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
            
            async for chunk in await self.client.search(prompt, mode=config["mode"], model=config["model"], stream=True, follow_up=follow_up):
                last_chunk = chunk
                # 思考/搜索阶段发送 keep-alive / Send keep-alive during thinking phase
                if "answer" not in chunk:
                    yield ": keepalive\n\n"
                    continue
                if "answer" in chunk:
                    full_answer = chunk['answer']
                    # We do NOT stream text deltas yet, because we might need to suppress them if it's a tool call
                    # 我们暂时不发送文本增量，因为如果是工具调用，我们需要将其作为工具调用发送而不是文本
                    # IMPORTANT: Send keep-alive to prevent client timeout during long answer generation
                    yield ": keepalive buffering\n\n"
                    
            # Save session / 保存会话
            if last_chunk:
                self._save_session(session_id, last_chunk)
                
            # Check for tool call / 检查工具调用
            tool_data = self._parse_tool_call(full_answer, tools)
            
            if tool_data:
                tool_call, tc_start, tc_end = tool_data
                block_index = 0
                
                # Stream preceding text (thinking / context) as a text block first
                # 先以文本块形式流式输出工具调用前的文本（思考/上下文）
                pre_text = full_answer[:tc_start].strip()
                if pre_text:
                    yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': block_index, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
                    yield f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': block_index, 'delta': {'type': 'text_delta', 'text': pre_text}})}\n\n"
                    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': block_index})}\n\n"
                    block_index += 1
                
                # Send tool_use content block
                tool_use_id = f"toolu_{uuid4().hex[:15]}"
                
                yield f"event: content_block_start\ndata: {json.dumps({
                    'type': 'content_block_start',
                    'index': block_index,
                    'content_block': {
                        'type': 'tool_use',
                        'id': tool_use_id,
                        'name': tool_call['name'],
                        'input': tool_call['input']
                    }
                })}\n\n"
                
                yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': block_index})}\n\n"
                
                # Message delta with stop_reason tool_use
                yield f"event: message_delta\ndata: {json.dumps({
                    'type': 'message_delta',
                    'delta': {'stop_reason': 'tool_use', 'stop_sequence': None},
                    'usage': {'output_tokens': len(full_answer) // 4}
                })}\n\n"
                
            else:
                # It's normal text -> Send text content block
                
                # 1. Content block start (text)
                yield f"event: content_block_start\ndata: {json.dumps({
                    'type': 'content_block_start',
                    'index': 0,
                    'content_block': {'type': 'text', 'text': ''}
                })}\n\n"
                
                # 2. Content block delta (full text)
                if full_answer:
                    yield f"event: content_block_delta\ndata: {json.dumps({
                        'type': 'content_block_delta',
                        'index': 0,
                        'delta': {'type': 'text_delta', 'text': full_answer}
                    })}\n\n"
                
                # 3. Content block stop
                yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
                
                # 4. Message delta with stop_reason end_turn
                yield f"event: message_delta\ndata: {json.dumps({
                    'type': 'message_delta',
                    'delta': {'stop_reason': 'end_turn', 'stop_sequence': None},
                    'usage': {'output_tokens': len(full_answer) // 4}
                })}\n\n"
                
            yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
            
        except Exception as e:
            bridge_logger.error(f"[Claude Stream] Error in stream generator: {type(e).__name__}: {e}", exc_info=True)
            # Try to send error event if possible
            try:
                error_msg = f"Stream error: {type(e).__name__}: {str(e)}"
                yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': {'type': 'server_error', 'message': error_msg}})}\n\n"
            except Exception:
                pass


    # --- Gemini Translation ---

    async def handle_gemini(self, model: str, request: GeminiGenerateContentRequest, session_id: str = None) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        await self.ensure_client()
        follow_up = self._get_follow_up(session_id)
        
        config = self._map_model(model)
        prompt = self._format_gemini_prompt(request)
        
        # Gemini streaming usually uses a different endpoint, but we'll handle it here if possible.
        # For now, let's just implement the non-streaming one.
        
        resp = await self.client.search(prompt, mode=config["mode"], model=config["model"], follow_up=follow_up)
        self._save_session(session_id, resp)
        
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

    async def handle_gemini_stream(self, model: str, request: GeminiGenerateContentRequest, session_id: str = None) -> AsyncGenerator[str, None]:
        """
        Handle Gemini streaming generateContent request. /
        处理 Gemini 流式生成请求。
        """
        await self.ensure_client()
        follow_up = self._get_follow_up(session_id)

        config = self._map_model(model)
        prompt = self._format_gemini_prompt(request)

        log_request_params("Gemini Stream", {
            "model": model,
            "mapped_config": config,
            "prompt_length": len(prompt),
            "session_id": session_id,
        })
        log_model_mapping(model, config)
        log_formatted_prompt(prompt)
        log_perplexity_request(config["mode"], config.get("model"), True)

        return self._stream_gemini(model, prompt, config, session_id=session_id, follow_up=follow_up)

    async def _stream_gemini(self, model: str, prompt: str, config: Dict[str, Any], session_id: str = None, follow_up: dict = None) -> AsyncGenerator[str, None]:
        """
        Generate Gemini SSE streaming chunks. /
        生成 Gemini SSE 流式响应块。
        """
        bridge_logger.info(f"[Gemini Stream] 开始流式响应 / Starting stream")
        flush_logs()

        last_sent_text = ""
        chunk_count = 0
        last_chunk = None

        async for chunk in await self.client.search(prompt, mode=config["mode"], model=config["model"], stream=True, follow_up=follow_up):
            last_chunk = chunk
            log_perplexity_response(chunk, is_chunk=True)

            # 思考/搜索阶段发送 keep-alive / Send keep-alive during thinking phase
            if "answer" not in chunk:
                yield ": keepalive\n\n"
                continue

            if "answer" in chunk:
                full_answer = chunk["answer"]
                delta_content = full_answer[len(last_sent_text):]

                if delta_content:
                    gemini_chunk = {
                        "candidates": [{
                            "content": {
                                "role": "model",
                                "parts": [{"text": delta_content}]
                            },
                            "index": 0,
                        }],
                    }
                    last_sent_text = full_answer
                    chunk_count += 1
                    yield f"data: {json.dumps(gemini_chunk)}\n\n"

        # 保存会话 / Save session
        if last_chunk:
            self._save_session(session_id, last_chunk)

        # 发送最终块 / Send final chunk with finishReason
        final_chunk = {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [{"text": ""}]
                },
                "finishReason": "STOP",
                "index": 0,
            }],
            "usageMetadata": {
                "promptTokenCount": len(prompt) // 4,
                "candidatesTokenCount": len(last_sent_text) // 4,
                "totalTokenCount": (len(prompt) + len(last_sent_text)) // 4
            }
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"

        bridge_logger.info(f"[Gemini Stream] 流式响应完成 / Stream completed, total_chunks={chunk_count}")
        flush_logs()
