# Importing necessary modules / 导入必要的模块
# re: Regular expressions for pattern matching / re: 用于模式匹配的正则表达式
# time: Time-related functions / time: 时间相关函数
# threading: For running background tasks / threading: 用于运行后台任务
# urllib.parse: URL parsing utilities / urllib.parse: URL 解析工具
# curl_cffi: HTTP requests / curl_cffi: HTTP 请求
# playwright.sync_api: Browser automation (standard) / playwright.sync_api: 浏览器自动化 (标准)
# patchright.sync_api: Undetected browser automation / patchright.sync_api: 未被检测的浏览器自动化
import re
import time
from threading import Thread
from urllib.parse import unquote
from curl_cffi import requests
from playwright.sync_api import sync_playwright
from patchright.sync_api import sync_playwright as sync_patchright
from .emailnator import Emailnator


class Driver:
    """Automate Perplexity AI account creation via browser workflows. / 通过浏览器工作流自动化创建 Perplexity AI 账号。"""

    def __init__(self):
        # Regular expression for extracting sign-in links / 用于提取登录链接的正则表达式
        self.signin_regex = re.compile(
            r'"(https://www\\.perplexity\\.ai/api/auth/callback/email\\?' r'callbackUrl=.*?)"'
        )

        # Flags and state variables / 标志和状态变量
        self.creating_new_account = False
        self.account_creator_running = False
        self.renewing_emailnator_cookies = False
        self.background_pages = []  # List of background browser pages / 后台浏览器页面列表
        self.perplexity_cookies = None  # Cookies for Perplexity AI / Perplexity AI 的 Cookies
        self.emailnator_cookies = None  # Cookies for Emailnator / Emailnator 的 Cookies

    def account_creator(self):
        """
        Background task for creating new accounts. / 用于创建新账号的后台任务。
        """
        self.new_account_link = None

        while True:
            if not self.new_account_link:
                print("Creating new account")

                while True:
                    try:
                        # Initialize Emailnator client / 初始化 Emailnator 客户端
                        emailnator_cli = Emailnator(
                            self.emailnator_cookies,
                            {
                                **self.emailnator_headers,
                                "x-xsrf-token": unquote(self.emailnator_cookies["XSRF-TOKEN"]),
                            },
                        )

                        # Send a POST request to initiate account creation / 发送 POST 请求以启动账号创建
                        resp = requests.post(
                            "https://www.perplexity.ai/api/auth/signin/email",
                            data={
                                "email": emailnator_cli.email,
                                "csrfToken": self.perplexity_cookies["next-auth.csrf-token"].split(
                                    "%"
                                )                        [0],
                                "callbackUrl": "https://www.perplexity.ai/",
                                "json": "true",
                            },
                            headers=self.perplexity_headers,
                            cookies=self.perplexity_cookies,
                        )

                        # Check if the response is successful / 检查响应是否成功
                        if resp.ok:
                            new_msgs = emailnator_cli.reload(
                                wait_for=lambda x: x["subject"] == "Sign in to Perplexity",
                                timeout=20,
                            )

                            if new_msgs:
                                msg = emailnator_cli.get(
                                    func=lambda x: x["subject"] == "Sign in to Perplexity"
                                )
                                self.new_account_link = self.signin_regex.search(
                                    emailnator_cli.open(msg["messageID"])
                                ).group(1)

                                print("New account created\n")
                                break

                    except Exception as e:
                        print("Account creation error", e)
                        print("Renewing emailnator cookies")

                        # Reset Emailnator cookies and wait for renewal / 重置 Emailnator cookies 并等待续费/更新
                        self.emailnator_cookies = None
                        self.renewing_emailnator_cookies = True

                        while not self.emailnator_cookies:
                            time.sleep(0.1)

            else:
                time.sleep(1)

    def intercept_request(self, route, request):
        """
        Intercepts browser requests to manage cookies and account creation. / 拦截浏览器请求以管理 cookies 和账号创建。
        """
        if self.renewing_emailnator_cookies and request.url != "https://www.emailnator.com/":
            self.page.goto("https://www.emailnator.com/")
            return

        if request.url == "https://www.perplexity.ai/":
            response = route.fetch()

            # Extract cookies from the request
            cookies = {
                x.split("=")[0]: x.split("=")[1] for x in request.headers["cookie"].split("; ")
            }

            if (
                not self.perplexity_cookies
                and "What do you want to know?" in response.text()
                and "next-auth.csrf-token" in cookies
            ):
                self.perplexity_headers = request.headers
                self.perplexity_cookies = cookies

                route.fulfill(body=":)")

                # Open a new page for Emailnator / 为 Emailnator 打开新页面
                self.background_pages.append(self.page)
                self.page = self.browser.new_page()
                self.page.route("**/*", self.intercept_request)
                self.page.goto("https://www.emailnator.com/")

            else:
                route.fulfill(response=response)

        elif request.url == "https://www.emailnator.com/":
            request_will_interrupt = False

            if self.renewing_emailnator_cookies:
                request_will_interrupt = True
                self.renewing_emailnator_cookies = False

            response = route.fetch()

            # Extract cookies from the request
            cookies = {
                x.split("=")[0]: x.split("=")[1] for x in request.headers["cookie"].split("; ")
            }

            if (
                not self.emailnator_cookies
                and "Temporary Disposable Gmail | Temp Mail | Email Generator" in response.text()
                and "XSRF-TOKEN" in cookies
            ):
                self.emailnator_headers = request.headers
                self.emailnator_cookies = cookies

                route.fulfill(body=":)")

                if not self.account_creator_running:
                    self.account_creator_running = True
                    Thread(target=self.account_creator).start()

                if request_will_interrupt:
                    self.page.goto("https://www.perplexity.ai/")
                    return

                # Open a new page for Perplexity AI / 为 Perplexity AI 打开新页面
                self.background_pages.append(self.page)
                self.page = self.browser.new_page()
                self.page.route("**/*", self.intercept_request)

                for page in self.background_pages:
                    page.close()

                while not self.new_account_link:
                    self.page.wait_for_timeout(1000)

                self.page.goto(self.new_account_link)
                self.page.goto("https://www.perplexity.ai/")
                self.new_account_link = None

            else:
                route.fulfill(response=response)

        elif "/rest/rate-limit" in request.url:
            route.continue_()
            gpt4_limit = request.response().json()["remaining"]

            if not self.creating_new_account and gpt4_limit == 0:
                self.creating_new_account = True
                self.page = self.browser.new_page()
                self.page.route("**/*", self.intercept_request)

                while not self.new_account_link:
                    self.page.wait_for_timeout(1000)

                self.page.goto(self.new_account_link)
                self.page.goto("https://www.perplexity.ai/")
                self.new_account_link = None

        else:
            route.continue_()

    def run(self, chrome_data_dir, port=None):
        """
        Launches the browser and starts intercepting requests. / 启动浏览器并开始拦截请求。

        Parameters:
        - chrome_data_dir: Path to the Chrome user data directory. / Chrome 用户数据目录的路径。
        - port: Port for remote debugging (optional). / 远程调试端口（可选）。
        """
        with sync_playwright() if port else sync_patchright() as playwright:
            if port:
                # Connect to an existing Chrome instance / 连接到现有的 Chrome 实例
                self.browser = playwright.chromium.connect_over_cdp(f"http://localhost:{port}")
            else:
                # Launch a new Chrome instance / 启动新的 Chrome 实例
                self.browser = playwright.chromium.launch_persistent_context(
                    user_data_dir=chrome_data_dir,
                    channel="chrome",
                    headless=False,
                    no_viewport=True,
                )

            self.page = self.browser.contexts[0].new_page() if port else self.browser.new_page()
            self.background_pages.append(self.page)
            self.page.route("**/*", self.intercept_request)
            self.page.goto("https://www.perplexity.ai/")

            while True:
                try:
                    self.page.context.pages[-1].wait_for_timeout(1000)
                except Exception:
                    pass
