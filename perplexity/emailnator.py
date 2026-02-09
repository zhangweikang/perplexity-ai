# Importing necessary modules / 导入必要的模块
# time: Time-related functions for delays and timeouts / time: 用于延迟和超时的相关时间函数
# urllib.parse: URL parsing utilities / urllib.parse: URL 解析工具
# curl_cffi: HTTP requests / curl_cffi: HTTP 请求
import time
from urllib.parse import unquote

from curl_cffi import requests

from .config import (
    EMAILNATOR_GENERATE_ENDPOINT,
    EMAILNATOR_HEADERS,
    EMAILNATOR_MESSAGE_LIST_ENDPOINT,
)


class Emailnator:
    """Disposable-email helper built on top of Emailnator. / 基于 Emailnator 构建的一次性电子邮件辅助工具。"""

    def __init__(
        self,
        cookies,
        headers={},
        domain=False,
        plus=False,
        dot=False,
        google_mail=True,
    ):
        # Initialize inbox and advertisement inbox / 初始化收件箱和广告收件箱
        self.inbox = []
        self.inbox_ads = []

        # Set default headers if not provided / 如果未提供，则设置默认请求头
        if not headers:
            headers = EMAILNATOR_HEADERS.copy()
            headers["x-xsrf-token"] = unquote(cookies["XSRF-TOKEN"])

        # Initialize HTTP session / 初始化 HTTP 会话
        self.s = requests.Session(headers=headers, cookies=cookies)

        # Prepare email generation options / 准备电子邮件生成选项
        data = {"email": []}
        if domain:
            data["email"].append("domain")
        if plus:
            data["email"].append("plusGmail")
        if dot:
            data["email"].append("dotGmail")
        if google_mail:
            data["email"].append("googleMail")

        # Generate a new email address / 生成新的电子邮件地址
        while True:
            resp = self.s.post(EMAILNATOR_GENERATE_ENDPOINT, json=data).json()
            if "email" in resp:
                break

        self.email = resp["email"][0]  # Store the generated email address / 存储生成的电子邮件地址

        # Load initial inbox advertisements / 加载初始收件箱广告
        for ads in self.s.post(
            EMAILNATOR_MESSAGE_LIST_ENDPOINT,
            json={"email": self.email},
        ).json()["messageData"]:
            self.inbox_ads.append(ads["messageID"])

    def reload(self, wait=False, retry=5, timeout=30, wait_for=None):
        """
        Reloads the inbox to fetch new messages. / 重新加载收件箱以获取新消息。

        Parameters:
        - wait: Whether to wait for new messages. / 是否等待新消息。
        - retry: Retry interval in seconds. / 重试间隔（秒）。
        - timeout: Maximum wait time in seconds. / 最大等待时间（秒）。
        - wait_for: A function to filter messages. / 用于过滤消息的函数。

        Returns:
        - List of new messages. / 新消息列表。
        """
        self.new_msgs = []
        start = time.time()
        wait_for_found = False

        while True:
            # Fetch messages from the inbox / 从收件箱中获取消息
            for msg in self.s.post(
                EMAILNATOR_MESSAGE_LIST_ENDPOINT,
                json={"email": self.email},
            ).json()["messageData"]:
                if msg["messageID"] not in self.inbox_ads and msg not in self.inbox:
                    self.new_msgs.append(msg)

                    if wait_for and wait_for(msg):
                        wait_for_found = True

            if (wait and not self.new_msgs) or wait_for:
                if wait_for_found:
                    break

                if time.time() - start > timeout:
                    return

                time.sleep(retry)
            else:
                break

        self.inbox += self.new_msgs  # Update the inbox with new messages / 使用新消息更新收件箱
        return self.new_msgs

    def open(self, msg_id):
        """
        Opens a specific message by its ID. / 通过 ID 打开特定消息。

        Parameters:
        - msg_id: The ID of the message to open. / 要打开的消息 ID。

        Returns:
        - The content of the message. / 消息内容。
        """
        return self.s.post(
            EMAILNATOR_MESSAGE_LIST_ENDPOINT,
            json={"email": self.email, "messageID": msg_id},
        ).text

    def get(self, func, msgs=[]):
        """
        Retrieves a message that matches a given condition. / 检索符合给定条件的邮件。

        Parameters:
        - func: A function to filter messages. / 用于过滤消息的函数。
        - msgs: List of messages to search (default: inbox). / 要搜索的消息列表 (默认：收件箱)。

        Returns:
        - The first message that matches the condition. / 第一个符合条件的邮件。
        """
        for msg in (msgs if msgs else self.inbox):
            if func(msg):
                return msg
