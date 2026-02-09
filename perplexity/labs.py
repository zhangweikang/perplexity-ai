# Importing necessary modules / 导入必要的模块
# ssl: SSL/TLS support for secure connections / ssl: 用于安全连接的 SSL/TLS 支持
# json: JSON parsing and serialization / json: JSON 解析和序列化
# time: Time-related functions for delays / time: 用于延迟的时间相关函数
# socket: Low-level networking interface / socket: 低级网络接口
# random: Random number generation / random: 随机数生成
# threading: For running background tasks / threading: 用于运行后台任务
# curl_cffi: HTTP requests / curl_cffi: HTTP 请求
# websocket: WebSocket client for real-time communication / websocket: 用于实时通信的 WebSocket 客户端
import json
import random
import socket
import ssl
import time
from threading import Thread

from curl_cffi import requests
from websocket import WebSocketApp

from .config import DEFAULT_HEADERS, ENDPOINT_SOCKET_IO


class LabsClient:
    """
    A client for interacting with the Perplexity AI Labs API. / 用于与 Perplexity AI Labs API 交互的客户端。
    """

    def __init__(self):
        # Initialize HTTP session with default headers / 使用默认请求头初始化 HTTP 会话
        self.session = requests.Session(headers=DEFAULT_HEADERS.copy())

        # Generate a unique timestamp for session identification / 生成用于会话识别的唯一时间戳
        self.timestamp = format(random.getrandbits(32), "08x")

        # Establish a session with the Perplexity Labs API / 建立与 Perplexity Labs API 的会话
        poll_url = f"{ENDPOINT_SOCKET_IO}?EIO=4&transport=polling&t={self.timestamp}"
        self.sid = json.loads(self.session.get(poll_url).text[1:])["sid"]
        self.last_answer = None  # Store the last response from the API / 存储来自 API 的最后一条响应
        self.history = []  # Maintain a history of queries and responses / 维护查询和响应的历史记录

        # Authenticate the session / 验证会话
        auth_url = (
            f"{ENDPOINT_SOCKET_IO}?EIO=4&transport=polling" f"&t={self.timestamp}&sid={self.sid}"
        )
        assert self.session.post(auth_url, data='40{"jwt":"anonymous-ask-user"}').text == "OK"

        # Set up a secure WebSocket connection / 设置安全 WebSocket 连接
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        self.sock = context.wrap_socket(
            socket.create_connection(("www.perplexity.ai", 443)),
            server_hostname="www.perplexity.ai",
        )

        # Initialize WebSocket client / 初始化 WebSocket 客户端
        websocket_url = (
            "wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket" f"&sid={self.sid}"
        )
        self.ws = WebSocketApp(
            url=websocket_url,
            header={"User-Agent": self.session.headers["User-Agent"]},
            cookie="; ".join(
                [f"{key}={value}" for key, value in self.session.cookies.get_dict().items()]
            ),
            on_open=lambda ws: (ws.send("2probe"), ws.send("5")),
            on_message=self._on_message,
            on_error=lambda ws, error: print(f"Websocket Error: {error}"),
            socket=self.sock,
        )

        # Run the WebSocket client in a separate thread / 在单独的线程中运行 WebSocket 客户端
        Thread(target=self.ws.run_forever, daemon=True).start()

        # Wait until the WebSocket connection is established / 等待 WebSocket 连接建立
        while not (self.ws.sock and self.ws.sock.connected):
            time.sleep(0.01)

    def _on_message(self, ws, message):
        """
        WebSocket message handler. / WebSocket 消息处理器。
        """
        if message == "2":
            ws.send("3")  # Respond to ping messages / 响应 ping 消息

        if message.startswith("42"):
            response = json.loads(message[2:])[1]

            if "final" in response:
                self.last_answer = response

    def ask(self, query, model="r1-1776", stream=False):
        """
        Sends a query to the Perplexity Labs API. / 向 Perplexity Labs API 发送查询。

        Parameters:
        - query: The query string. / 查询字符串。
        - model: The model to use for the query. / 用于查询的模型。
        - stream: Whether to stream the response. / 是否流式传输响应。

        Returns:
        - The final response or a generator for streaming responses. / 最终响应或流式响应的生成器。
        """
        assert model in [
            "r1-1776",
            "sonar-pro",
            "sonar",
            "sonar-reasoning-pro",
            "sonar-reasoning",
        ], "Invalid model."

        self.last_answer = None
        self.history.append({"role": "user", "content": query})

        # Send the query via WebSocket / 通过 WebSocket 发送查询
        self.ws.send(
            "42"
            + json.dumps(
                [
                    "perplexity_labs",
                    {
                        "messages": self.history,
                        "model": model,
                        "source": "default",
                        "version": "2.18",
                    },
                ]
            )
        )

        def stream_response():
            """
            Generator for streaming responses. / 用于流式响应的生成器。
            """
            answer = None

            while True:
                if self.last_answer != answer:
                    answer = self.last_answer
                    yield answer

                if self.last_answer and self.last_answer.get("final"):
                    answer = self.last_answer
                    self.last_answer = None
                    self.history.append(
                        {
                            "role": "assistant",
                            "content": answer["output"],
                            "priority": 0,
                        }
                    )

                    return

                time.sleep(0.01)

        if stream:
            return stream_response()

        while True:
            if self.last_answer and self.last_answer.get("final"):
                answer = self.last_answer
                self.last_answer = None
                self.history.append(
                    {
                        "role": "assistant",
                        "content": answer["output"],
                        "priority": 0,
                    }
                )

                return answer

            time.sleep(0.01)
