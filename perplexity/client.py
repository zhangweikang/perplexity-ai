# Importing necessary modules / 导入必要的模块
# re: Regular expressions for pattern matching / re: 用于模式匹配的正则表达式
# sys: System-specific parameters and functions / sys: 系统特定的参数和函数
# json: JSON parsing and serialization / json: JSON 解析和序列化
# random: Random number generation / random: 随机数生成
# mimetypes: Guessing MIME types of files / mimetypes: 猜测文件的 MIME 类型
# uuid: Generating unique identifiers / uuid: 生成唯一标识符
# curl_cffi: HTTP requests and multipart form data handling / curl_cffi: HTTP 请求和多部分表单数据处理
import re
import sys
import json
import random
import mimetypes
from uuid import uuid4
from curl_cffi import CurlMime, requests

from .config import (
    DEFAULT_HEADERS,
    ENDPOINT_AUTH_SESSION,
    ENDPOINT_AUTH_SIGNIN,
    ENDPOINT_SSE_ASK,
    ENDPOINT_UPLOAD_URL,
    MODEL_MAPPINGS,
)
from .emailnator import Emailnator


class Client:
    """
    A client for interacting with the Perplexity AI API.
    """

    def __init__(self, cookies={}):
        # Initialize an HTTP session with default headers and optional cookies / 使用默认头和可选的 cookies 初始化 HTTP 会话
        self.session = requests.Session(
            headers=DEFAULT_HEADERS.copy(),
            cookies=cookies,
            impersonate="chrome",
        )

        # Flags and counters for account and query management / 账号和查询管理的标志及计数器
        self.own = bool(cookies)  # Indicates if the client uses its own account / 指示客户端是否使用自己的账号
        self.copilot = 0 if not cookies else float("inf")  # Remaining pro queries / 剩余的 pro 查询次数
        self.file_upload = 0 if not cookies else float("inf")  # Remaining file uploads / 剩余的文件上传次数

        # Regular expression for extracting sign-in links / 用于提取登录链接的正则表达式
        self.signin_regex = re.compile(
            r'"(https://www\\.perplexity\\.ai/api/auth/callback/email\\?' r'callbackUrl=.*?)"'
        )

        # Unique timestamp for session identification / 用于会话识别的唯一时间戳
        self.timestamp = format(random.getrandbits(32), "08x")

        # Initialize session by making a GET request / 通过发起 GET 请求初始化会话
        self.session.get(ENDPOINT_AUTH_SESSION)

    def create_account(self, cookies):
        """
        Creates a new account using Emailnator cookies.
        """
        while True:
            try:
                # Initialize Emailnator client / 初始化 Emailnator 客户端
                emailnator_cli = Emailnator(cookies)

                # Send a POST request to initiate account creation / 发送 POST 请求以启动账号创建
                resp = self.session.post(
                    ENDPOINT_AUTH_SIGNIN,
                    data={
                        "email": emailnator_cli.email,
                        "csrfToken": self.session.cookies.get_dict()["next-auth.csrf-token"].split(
                            "%"
                        )[0],
                        "callbackUrl": "https://www.perplexity.ai/",
                        "json": "true",
                    },
                )

                # Check if the response is successful / 检查响应是否成功
                if resp.ok:
                    # Wait for the sign-in email to arrive / 等待登录邮件到达
                    new_msgs = emailnator_cli.reload(
                        wait_for=lambda x: x["subject"] == "Sign in to Perplexity",
                        timeout=20,
                    )

                    if new_msgs:
                        break
                else:
                    print("Perplexity account creating error:", resp)

            except Exception:
                pass

        # Extract the sign-in link from the email / 从电子邮件中提取登录链接
        msg = emailnator_cli.get(func=lambda x: x["subject"] == "Sign in to Perplexity")
        new_account_link = self.signin_regex.search(emailnator_cli.open(msg["messageID"])).group(1)

        # Complete the account creation process / 完成账号创建过程
        self.session.get(new_account_link)

        # Update query and file upload limits / 更新查询和文件上传限制
        self.copilot = 5
        self.file_upload = 10

        return True

    def search(
        self,
        query,
        mode="auto",
        model=None,
        sources=["web"],
        files={},
        stream=False,
        language="zh-CN",
        follow_up=None,
        incognito=False,
    ):
        """
        Executes a search query on Perplexity AI.

        Parameters:
        - query: The search query string.
        - mode: Search mode ('auto', 'pro', 'reasoning', 'deep research').
        - model: Specific model to use for the query.
        - sources: List of sources ('web', 'scholar', 'social').
        - files: Dictionary of files to upload.
        - stream: Whether to stream the response.
        - language: Language code (ISO 639).
        - follow_up: Information for follow-up queries.
        - incognito: Whether to enable incognito mode.
        """
        # Validate input parameters / 验证输入参数
        assert mode in [
            "auto",
            "pro",
            "reasoning",
            "deep research",
        ], "Invalid search mode."
        assert (
            model
            in {
                "auto": [None],
                "pro": list(MODEL_MAPPINGS["pro"].keys()),
                "reasoning": list(MODEL_MAPPINGS["reasoning"].keys()),
                "deep research": [None],
            }[mode]
            if self.own
            else True
        ), "Invalid model for the selected mode."
        assert all(
            [source in ("web", "scholar", "social") for source in sources]
        ), "Invalid sources."
        assert (
            self.copilot > 0 if mode in ["pro", "reasoning", "deep research"] else True
        ), "No remaining pro queries."
        assert self.file_upload - len(files) >= 0 if files else True, "File upload limit exceeded."

        # Update query and file upload counters / 更新查询和文件上传计数器
        self.copilot = (
            self.copilot - 1 if mode in ["pro", "reasoning", "deep research"] else self.copilot
        )
        self.file_upload = self.file_upload - len(files) if files else self.file_upload

        # Upload files and prepare the query payload / 上传文件并准备查询负载
        uploaded_files = []
        for filename, file in files.items():
            file_type = mimetypes.guess_type(filename)[0]
            file_upload_info = (
                self.session.post(
                    ENDPOINT_UPLOAD_URL,
                    params={"version": "2.18", "source": "default"},
                    json={
                        "content_type": file_type,
                        "file_size": sys.getsizeof(file),
                        "filename": filename,
                        "force_image": False,
                        "source": "default",
                    },
                )
            ).json()

            # Upload the file to the server / 将文件上传到服务器
            mp = CurlMime()
            for key, value in file_upload_info["fields"].items():
                mp.addpart(name=key, data=value)
            mp.addpart(
                name="file",
                content_type=file_type,
                filename=filename,
                data=file,
            )

            upload_resp = self.session.post(file_upload_info["s3_bucket_url"], multipart=mp)

            if not upload_resp.ok:
                raise Exception("File upload error", upload_resp)

            # Extract the uploaded file URL / 提取已上传文件的 URL
            if "image/upload" in file_upload_info["s3_object_url"]:
                uploaded_url = re.sub(
                    r"/private/s--.*?--/v\\d+/user_uploads/",
                    "/private/user_uploads/",
                    upload_resp.json()["secure_url"],
                )
            else:
                uploaded_url = file_upload_info["s3_object_url"]

            uploaded_files.append(uploaded_url)

        # Prepare the JSON payload for the query / 准备查询的 JSON 负载
        json_data = {
            "query_str": query,
            "params": {
                "attachments": (
                    uploaded_files + follow_up["attachments"] if follow_up else uploaded_files
                ),
                "frontend_context_uuid": str(uuid4()),
                "frontend_uuid": str(uuid4()),
                "is_incognito": incognito,
                "language": language,
                "last_backend_uuid": (follow_up["backend_uuid"] if follow_up else None),
                "mode": "concise" if mode == "auto" else "copilot",
                "model_preference": MODEL_MAPPINGS[mode][model],
                "source": "default",
                "sources": sources,
                "version": "2.18",
            },
        }

        # Send the query request and handle the response / 发送查询请求并处理响应
        resp = self.session.post(ENDPOINT_SSE_ASK, json=json_data, stream=True)
        chunks = []

        def stream_response(resp):
            """
            Generator for streaming responses.
            """
            for chunk in resp.iter_lines(delimiter=b"\r\n\r\n"):
                content = chunk.decode("utf-8")

                if content.startswith("event: message\r\n"):
                    try:
                        content_json = json.loads(content[len("event: message\r\ndata: ") :])

                        # Parse the nested 'text' field if it exists / 如果存在嵌套的 'text' 字段则进行解析
                        if "text" in content_json and content_json["text"]:
                            try:
                                text_parsed = json.loads(content_json["text"])
                                # Extract answer from FINAL step if available / 如果有 FINAL 步骤，从中提取答案
                                if isinstance(text_parsed, list):
                                    for step in text_parsed:
                                        if step.get("step_type") == "FINAL":
                                            final_content = step.get("content", {})
                                            if "answer" in final_content:
                                                answer_data = json.loads(final_content["answer"])
                                                content_json["answer"] = answer_data.get(
                                                    "answer", ""
                                                )
                                                content_json["chunks"] = answer_data.get(
                                                    "chunks", []
                                                )
                                                break
                                content_json["text"] = text_parsed
                            except (json.JSONDecodeError, TypeError, KeyError):
                                pass

                        chunks.append(content_json)
                        yield chunks[-1]
                    except (json.JSONDecodeError, KeyError):
                        continue

                elif content.startswith("event: end_of_stream\r\n"):
                    return

        if stream:
            return stream_response(resp)

        for chunk in resp.iter_lines(delimiter=b"\r\n\r\n"):
            content = chunk.decode("utf-8")

            if content.startswith("event: message\r\n"):
                try:
                    content_json = json.loads(content[len("event: message\r\ndata: ") :])

                    # Parse the nested 'text' field if it exists / 如果存在嵌套的 'text' 字段则进行解析
                    if "text" in content_json and content_json["text"]:
                        try:
                            text_parsed = json.loads(content_json["text"])
                            # Extract answer from FINAL step if available / 如果有 FINAL 步骤，从中提取答案
                            if isinstance(text_parsed, list):
                                for step in text_parsed:
                                    if step.get("step_type") == "FINAL":
                                        final_content = step.get("content", {})
                                        if "answer" in final_content:
                                            answer_data = json.loads(final_content["answer"])
                                            content_json["answer"] = answer_data.get("answer", "")
                                            content_json["chunks"] = answer_data.get("chunks", [])
                                            break
                            content_json["text"] = text_parsed
                        except (json.JSONDecodeError, TypeError, KeyError):
                            pass

                    chunks.append(content_json)
                except (json.JSONDecodeError, KeyError):
                    continue

            elif content.startswith("event: end_of_stream\r\n"):
                return chunks[-1] if chunks else {}
