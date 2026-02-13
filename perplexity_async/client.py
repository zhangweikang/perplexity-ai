import json
import mimetypes
import random
import re
import sys
from uuid import uuid4

from curl_cffi import CurlMime, requests

from perplexity.config import (
    DEFAULT_HEADERS,
    ENDPOINT_AUTH_SESSION,
    ENDPOINT_AUTH_SIGNIN,
    ENDPOINT_SSE_ASK,
    ENDPOINT_UPLOAD_URL,
    ENDPOINT_THREAD_LIST,
    ENDPOINT_THREAD_DETAIL,
    ENDPOINT_THREAD_DELETE,
    MODEL_MAPPINGS,
)
from perplexity.exceptions import AuthenticationError
from .emailnator import Emailnator


class AsyncMixin:
    def __init__(self, *args, **kwargs):
        self.__storedargs = args, kwargs
        self.async_initialized = False

    async def __ainit__(self, *args, **kwargs):
        pass

    async def __initobj(self):
        assert not self.async_initialized
        self.async_initialized = True

        # pass the parameters to __ainit__ that passed to __init__ / 将传递给 __init__ 的参数传递给 __ainit__
        await self.__ainit__(*self.__storedargs[0], **self.__storedargs[1])
        return self

    def __await__(self):
        return self.__initobj().__await__()


class Client(AsyncMixin):
    """
    A client for interacting with the Perplexity AI API. / 用于与 Perplexity AI API 交互的客户端。
    """

    async def __ainit__(self, cookies={}):
        self.session = requests.AsyncSession(
            headers=DEFAULT_HEADERS.copy(),
            cookies=cookies,
            impersonate="chrome124",
            timeout=300,  # 5分钟超时，防止 reasoning 模式思考时间过长导致连接中断
        )
        self.own = bool(cookies)
        self.copilot = 0 if not cookies else float("inf")
        self.file_upload = 0 if not cookies else float("inf")
        self.signin_regex = re.compile(
            r'"(https://www\.perplexity\.ai/api/auth/callback/email\?' r'callbackUrl=.*?)"'
        )
        self.timestamp = format(random.getrandbits(32), "08x")
        await self.session.get(ENDPOINT_AUTH_SESSION)

    async def create_account(self, cookies):
        """
        Function to create a new account / 创建新账号的函数
        """
        while True:
            try:
                emailnator_cli = await Emailnator(cookies)

                resp = await self.session.post(
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

                if resp.ok:
                    new_msgs = await emailnator_cli.reload(
                        wait_for=lambda x: x["subject"] == "Sign in to Perplexity",
                        timeout=20,
                    )

                    if new_msgs:
                        break
                else:
                    print("Perplexity account creating error:", resp)

            except Exception:
                pass

        msg = emailnator_cli.get(func=lambda x: x["subject"] == "Sign in to Perplexity")
        new_account_link = self.signin_regex.search(
            await emailnator_cli.open(msg["messageID"])
        ).group(1)

        await self.session.get(new_account_link)

        self.copilot = 5
        self.file_upload = 10

        return True

    async def search(
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
        Query function / 查询函数
        """
        assert mode in [
            "auto",
            "pro",
            "reasoning",
            "deep research",
        ], 'Search modes -> ["auto", "pro", "reasoning", "deep research"]'
        assert (
            model
            in {
                "auto": [None],
                "pro": list(MODEL_MAPPINGS["pro"].keys()),
                "reasoning": list(MODEL_MAPPINGS["reasoning"].keys()),
                "deep research": [None],
                "copilot": [None, "gemini-3.0-pro", "kimi-k2-thinking"],
            }[mode]
            if self.own
            else True
        ), "Invalid model for selected mode"
        assert all(
            [source in ("web", "scholar", "social") for source in sources]
        ), 'Sources -> ["web", "scholar", "social"]'
        assert (
            self.copilot > 0 if mode in ["pro", "reasoning", "deep research"] else True
        ), "You have used all of your enhanced (pro) queries"
        assert self.file_upload - len(files) >= 0 if files else True, (
            f"You tried to upload {len(files)} files but only "
            f"{self.file_upload} upload(s) remain."
        )

        self.copilot = (
            self.copilot - 1 if mode in ["pro", "reasoning", "deep research"] else self.copilot
        )
        self.file_upload = self.file_upload - len(files) if files else self.file_upload

        uploaded_files = []

        for filename, file in files.items():
            file_type = mimetypes.guess_type(filename)[0]
            file_upload_info = (
                await self.session.post(
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

            mp = CurlMime()
            for key, value in file_upload_info["fields"].items():
                mp.addpart(name=key, data=value)
            mp.addpart(
                name="file",
                content_type=file_type,
                filename=filename,
                data=file,
            )

            upload_resp = await self.session.post(file_upload_info["s3_bucket_url"], multipart=mp)

            if not upload_resp.ok:
                raise Exception("File upload error", upload_resp)

            if "image/upload" in file_upload_info["s3_object_url"]:
                uploaded_url = re.sub(
                    r"/private/s--.*?--/v\d+/user_uploads/",
                    "/private/user_uploads/",
                    upload_resp.json()["secure_url"],
                )
            else:
                uploaded_url = file_upload_info["s3_object_url"]

            uploaded_files.append(uploaded_url)

        json_data = {
            "query_str": query,
            "params": {
                "attachments": (
                    uploaded_files + follow_up.get("attachments", []) if follow_up else uploaded_files
                ),
                "frontend_context_uuid": str(uuid4()),
                "frontend_uuid": str(uuid4()),
                "is_incognito": incognito,
                "language": language,
                "last_backend_uuid": (follow_up.get("backend_uuid") if follow_up else None),
                "mode": "concise" if mode == "auto" else "copilot",
                "model_preference": MODEL_MAPPINGS[mode][model],
                "source": "default",
                "sources": sources,
                "version": "2.18",
            },
        }

        # Headers for API request to bypass Cloudflare
        api_headers = {
            "accept": "text/event-stream",
            "content-type": "application/json",
            "origin": "https://www.perplexity.ai",
            "referer": "https://www.perplexity.ai/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

        resp = await self.session.post(ENDPOINT_SSE_ASK, json=json_data, headers=api_headers, stream=True)
        if not resp.ok:
            print(f"Error: SSE request failed with status {resp.status_code}")
            print(f"Response: {resp.text}")
            if resp.status_code == 403:
                raise AuthenticationError("会话已失效,请重新设置会话信息")
            resp.raise_for_status()

        chunks = []

        async def stream_response(resp):
            print("Starting to stream response...")
            async for chunk in resp.aiter_lines(delimiter=b"\r\n\r\n"):
                content = chunk.decode("utf-8")
                # print(f"Raw chunk: {repr(content[:100])}...")

                if content.startswith("event: message"):
                    try:
                        # robust parsing for data: prefix
                        data_start = content.find("data: ")
                        if data_start == -1:
                            continue
                        content_json = json.loads(content[data_start + 6 :])

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

        async for chunk in resp.aiter_lines(delimiter=b"\r\n\r\n"):
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

    async def get_threads(self, limit=20, offset=0, search_term=""):
        """
        Fetches a list of threads from Perplexity AI.

        Parameters:
        - limit: Number of threads to fetch (default 20)
        - offset: Offset for pagination (default 0)
        - search_term: Search term to filter threads (default empty)
        """
        url = f"{ENDPOINT_THREAD_LIST}?version=2.18&source=default"
        payload = {"limit": limit, "offset": offset, "search_term": search_term}
        api_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "origin": "https://www.perplexity.ai",
            "referer": "https://www.perplexity.ai/",
        }
        resp = await self.session.post(url, json=payload, headers=api_headers)
        resp.raise_for_status()
        return resp.json()

    async def get_thread_details_by_slug(self, slug, query_params=None):
        """
        Fetches thread details using the provided slug from the new endpoint.

        Parameters:
        - slug: The thread slug (string)
        - query_params: Optional dict of query parameters to override defaults
        """
        from urllib.parse import urlencode

        default_params = {
            "with_parent_info": "true",
            "with_schematized_response": "true",
            "version": "2.18",
            "source": "default",
            "limit": 100,
            "offset": 0,
            "from_first": "true",
            "supported_block_use_cases": [
                "answer_modes",
                "media_items",
                "knowledge_cards",
                "inline_entity_cards",
                "place_widgets",
                "finance_widgets",
                "sports_widgets",
                "shopping_widgets",
                "jobs_widgets",
                "search_result_widgets",
                "clarification_responses",
                "inline_images",
                "inline_assets",
                "inline_finance_widgets",
                "placeholder_cards",
                "diff_blocks",
                "inline_knowledge_cards",
            ],
        }
        # Merge user params
        params = dict(default_params)
        if query_params:
            for k, v in query_params.items():
                params[k] = v
        # Handle list params for supported_block_use_cases
        query_items = []
        for k, v in params.items():
            if isinstance(v, list):
                for item in v:
                    query_items.append((k, item))
            else:
                query_items.append((k, v))
        query_string = urlencode(query_items)
        url = f"{ENDPOINT_THREAD_DETAIL}/{slug}?{query_string}"
        api_headers = {
            "accept": "application/json, text/plain, */*",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-requested-with": "XMLHttpRequest",
            "origin": "https://www.perplexity.ai",
            "referer": "https://www.perplexity.ai/",
        }
        resp = await self.session.get(url, headers=api_headers)
        resp.raise_for_status()
        return resp.json()

    async def delete_threads(self, uuids: list):
        """
        Delete multiple threads by iterating through their UUIDs. /
        通过循环遍历调用单条删除接口来批量删除对话。
        """
        url = f"{ENDPOINT_THREAD_DELETE}?version=2.18&source=default"
        api_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "origin": "https://www.perplexity.ai",
            "referer": "https://www.perplexity.ai/",
        }

        results = []
        for uuid in uuids:
            try:
                # Perplexity new delete API requires single entry_uuid and read_write_token
                payload = {"entry_uuid": uuid, "read_write_token": ""}
                resp = await self.session.delete(url, json=payload, headers=api_headers)
                resp.raise_for_status()
                try:
                    data = resp.json()
                except:
                    data = {}
                results.append({"uuid": uuid, "status": "success", "data": data})
            except Exception as e:
                results.append({"uuid": uuid, "status": "error", "error": str(e)})
        
        return {"results": results}
