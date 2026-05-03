"""
模块名称：Kimi 聊天发起自动化工具（kimi_chat_starter.py）

说明：
1. 本文件参考 fetch_himmpat.py 的整体框架重新搭建；
2. 当前项目目标站点为：https://www.kimi.com/；
3. 浏览器持久化缓存目录默认使用：D:\chromeCache；
4. 已实现打开页面、登录态检测、人工登录等待、输入文本、选择模型、点击发送等基础自动化流程；
5. 支持多个任务并发打开页面，并通过同一个持久化 Chrome 上下文共享登录态/缓存。

依赖安装：
    pip install playwright
    playwright install chromium

运行：
    python kimi_chat_starter.py
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Optional

from playwright.async_api import BrowserContext, Page, async_playwright


# =========================
# 基础配置区域
# =========================
KIMI_HOME_URL = "https://www.kimi.com/"
KIMI_USER_DATA_DIR = r"D:\chromeCache" # 浏览器缓存目录
KIMI_DEFAULT_MODEL_KEYWORD = "思考"
KIMI_PAGE_LOAD_TIMEOUT_SECONDS = 40  # 页面加载和业务动作等待超时，单位秒
KIMI_TOTAL_RETRY_TIMES = 3  # 页面加载、业务动作等总尝试次数
KIMI_MAX_CONCURRENCY = 3  # 默认最大并发任务数
KIMI_KEEP_BROWSER_OPEN_AFTER_SEND = True  # 任务内部是否主动关闭标签页；外层关闭浏览器上下文时仍会统一关闭


def kimi_wait_ms(seconds: int = KIMI_PAGE_LOAD_TIMEOUT_SECONDS) -> int:
    """将秒级等待时间转换为 Playwright 使用的毫秒。"""
    return seconds * 1000


@dataclass
class KimiTask:
    """
    Kimi 自动化任务结构。

    字段：
    - task_id：任务编号，用于日志输出和失败返回；
    - payload：任务载荷，支持 str，或包含 text/model_keyword 的 dict。
    """

    task_id: str
    payload: Any = None


class AsyncKimiScraper:
    """Kimi 页面操作器：负责浏览器上下文、并发调度、页面打开和消息发送。"""

    def __init__(
        self,
        user_data_dir: str = KIMI_USER_DATA_DIR,
        max_retries: int = KIMI_TOTAL_RETRY_TIMES,
    ):
        self.user_data_dir = user_data_dir
        self.max_retries = max_retries
        self.playwright = None
        self.context: Optional[BrowserContext] = None

    async def _create_context_async(self, playwright) -> BrowserContext:
        """创建持久化 Chrome 上下文，复用 self.user_data_dir 中的缓存和登录态。"""
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            channel="chrome",
            headless=False,
            java_script_enabled=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
            locale="zh-CN",
        )
        await context.set_extra_http_headers(
            {
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        return context

    async def _ensure_context_async(self) -> None:
        """确保 Playwright 与浏览器上下文已启动。"""
        if self.context is not None:
            return
        self.playwright = await async_playwright().start()
        self.context = await self._create_context_async(self.playwright)


    async def _wait_kimi_home_loaded_async(self, page: Page) -> str:
        """
        等待 Kimi 首页加载完成。

        判断标准：CSS 选择器 span.user-name 存在；
        如果不存在，认为页面没有加载出来，可能是网络、资源或站点问题。
        """
        await page.wait_for_selector(
            "span.user-name",
            state="attached",
            timeout=kimi_wait_ms(),
        )
        return await self._get_user_name_text_async(page)

    async def _get_user_name_text_async(self, page: Page) -> str:
        """读取 span.user-name 的文本，并去除头尾空格。"""
        locator = page.locator("span.user-name").first
        text = await locator.inner_text(timeout=kimi_wait_ms())
        return text.strip()

    async def _detect_login_status_async(self, page: Page) -> dict:
        """
        根据 span.user-name 文本判断当前是否已登录。

        返回：
        - is_logged_in：bool，True 表示已登录；
        - status_text：str，"已登录" 或 "未登录"；
        - user_name：str，页面上的用户名文本，未登录时通常为 "登录"。
        """
        user_name = await self._get_user_name_text_async(page)
        is_logged_in = user_name != "登录"
        status_text = "已登录" if is_logged_in else "未登录"
        print(f"当前 Kimi 登录状态判断为：{status_text}；span.user-name 文本：{user_name!r}")
        return {
            "is_logged_in": is_logged_in,
            "status_text": status_text,
            "user_name": user_name,
        }

    async def _click_login_and_wait_until_logged_in_async(self, page: Page) -> dict:
        """
        未登录时点击用户名区域，并循环等待用户人工完成登录。

        每 1 秒读取一次 span.user-name；当文本不再是 "登录" 时认为登录成功。

        返回：
        - is_logged_in：固定为 True；
        - status_text：固定为 "已登录"；
        - user_name：登录后的账号名称。
        """
        print("检测到当前未登录，准备点击 .user-name 打开登录入口。")
        await page.evaluate(
            """() => {
                const element = document.querySelector('.user-name');
                if (!element) {
                    throw new Error('未找到 .user-name，无法点击登录入口');
                }
                element.click();
            }"""
        )

        while True:
            await asyncio.sleep(1)
            user_name = await self._get_user_name_text_async(page)
            if user_name != "登录":
                print(f"检测到用户已完成登录；当前账号名称：{user_name!r}")
                return {
                    "is_logged_in": True,
                    "status_text": "已登录",
                    "user_name": user_name,
                }
            print(f"等待用户登录中；当前 span.user-name 文本仍为：{user_name!r}")

    async def _ensure_kimi_login_async(self, page: Page) -> dict:
        """检查登录状态；未登录则点击登录入口并等待人工登录完成。"""
        login_status = await self._detect_login_status_async(page)
        if login_status["is_logged_in"]:
            return login_status
        return await self._click_login_and_wait_until_logged_in_async(page)

    async def _wait_kimi_chat_editor_ready_async(self, page: Page) -> None:
        """
        等待输入框、模型名称、发送按钮三个元素都出现。

        这表示 Kimi 的聊天输入区已经准备好，可以继续输入和发送。
        """
        for selector in [
            '.chat-input-editor[contenteditable="true"], [data-lexical-editor="true"][contenteditable="true"], div[role="textbox"][contenteditable="true"]',
            ".model-name>.name",
            ".send-button-container",
        ]:
            await page.wait_for_selector(selector, state="attached", timeout=kimi_wait_ms())

    async def input_kimi_text_async(self, page: Page, text: str) -> str:
        """
        向 Kimi 输入框输入文本。

        这里使用已在控制台验证成功的实践：
        focus + selectAll + composition 事件 + execCommand('insertText') + input/change 事件。
        返回输入后页面输入框中的实际文本，方便调用方校验。
        """
        await self._wait_kimi_chat_editor_ready_async(page)
        return await page.evaluate(
            """async ({ selector, text }) => {
                const editor = document.querySelector(selector);
                if (!editor) {
                    throw new Error(`未找到 Kimi 输入框：${selector}`);
                }

                editor.scrollIntoView({ block: 'center', inline: 'nearest' });
                editor.focus();

                const range = document.createRange();
                range.selectNodeContents(editor);
                range.collapse(false);

                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);

                document.execCommand('selectAll', false, null);

                editor.dispatchEvent(new CompositionEvent('compositionstart', {
                    bubbles: true,
                    data: '',
                }));
                editor.dispatchEvent(new CompositionEvent('compositionupdate', {
                    bubbles: true,
                    data: text,
                }));

                document.execCommand('insertText', false, text);

                editor.dispatchEvent(new CompositionEvent('compositionend', {
                    bubbles: true,
                    data: text,
                }));
                editor.dispatchEvent(new InputEvent('beforeinput', {
                    bubbles: true,
                    cancelable: true,
                    inputType: 'insertCompositionText',
                    data: text,
                }));
                editor.dispatchEvent(new InputEvent('input', {
                    bubbles: true,
                    cancelable: false,
                    inputType: 'insertCompositionText',
                    data: text,
                }));
                editor.dispatchEvent(new Event('change', { bubbles: true }));

                return editor.innerText || editor.textContent || '';
            }""",
            {
                "selector": '.chat-input-editor[contenteditable="true"], [data-lexical-editor="true"][contenteditable="true"], div[role="textbox"][contenteditable="true"]',
                "text": text,
            },
        )

    async def select_kimi_model_async(self, page: Page, model_keyword: str = KIMI_DEFAULT_MODEL_KEYWORD) -> str:
        """
        按关键字选择 Kimi 模型，并返回最终显示的模型名称。

        如果模型列表中没有找到包含 model_keyword 的选项，则不主动报错，返回页面当前选中的模型名称。
        """
        await self._wait_kimi_chat_editor_ready_async(page)
        return await page.evaluate(
            """async (keyword) => {
                const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

                document.querySelector(".model-name>.name").click();
                await sleep(500);

                const items = document.querySelectorAll(".models-container .model-item");
                for (const item of items) {
                    const nameEl = item.querySelector(".model-name .name");
                    if (nameEl && nameEl.textContent.includes(keyword)) {
                        item.click();
                        await sleep(500);
                        break;
                    }
                }

                return document.querySelector(".model-name>.name").textContent.trim();
            }""",
            model_keyword,
        )

    async def click_kimi_send_button_async(self, page: Page) -> str:
        """点击 Kimi 发送按钮，等待 500 毫秒后返回当前页面地址。"""
        # 注意：不要在点击动作里重复判断发送按钮是否存在。
        # 页面元素存在性由 _wait_kimi_chat_editor_ready_async 统一负责，避免把页面加载判断逻辑散落到业务动作中。
        return await page.evaluate(
            """async (selector) => {
                const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
                document.querySelector(selector).click();
                await sleep(500);
                return window.location.href;
            }""",
            ".send-button-container",
        )

    async def send_kimi_message_async(
        self,
        page: Page,
        text: str,
        model_keyword: str = KIMI_DEFAULT_MODEL_KEYWORD,
    ) -> dict:
        """
        在已打开且已登录的 Kimi 页面中发送消息。

        流程：输入文本 → 按关键字选择模型 → 点击发送。

        返回：
        - input_text：写入输入框后的实际文本；
        - selected_model：发送前页面最终显示的模型名称；
        - url：点击发送后的当前页面地址。
        """
        input_text = await self.input_kimi_text_async(page, text)
        selected_model = await self.select_kimi_model_async(page, model_keyword)
        after_send_url = await self.click_kimi_send_button_async(page)
        return {
            "input_text": input_text.strip(),
            "selected_model": selected_model.strip(),
            "url": after_send_url,
        }


    async def open_kimi_page_and_send_async(self, task: KimiTask) -> dict:
        """
        为单个任务打开 Kimi 页面，确保登录后发送消息。

        task.payload 支持两种形式：
        1. str：直接作为要发送的文本，模型关键字默认使用“思考”；
        2. dict：读取 text 字段作为要发送的文本，读取 model_keyword 字段作为模型关键字。

        返回：
        - 成功：包含 task_id、title、login_status、user_name、input_text、selected_model、url；
        - 失败：包含 status=False、task_id、msg。
        """
        await self._ensure_context_async()
        assert self.context is not None

        model_keyword = KIMI_DEFAULT_MODEL_KEYWORD
        if isinstance(task.payload, dict):
            text = str(task.payload.get("text", ""))
            model_keyword = str(task.payload.get("model_keyword") or KIMI_DEFAULT_MODEL_KEYWORD)
        else:
            text = str(task.payload or "")
        if not text.strip():
            return {"status": False, "task_id": task.task_id, "msg": "发送文本不能为空"}

        page: Optional[Page] = None
        for attempt in range(self.max_retries):
            page = await self.context.new_page()
            try:
                print(f"[{task.task_id}] 打开 Kimi 并准备发送消息，第 {attempt + 1}/{self.max_retries} 次")
                await page.goto(KIMI_HOME_URL, wait_until="domcontentloaded", timeout=kimi_wait_ms())
                user_name_text = await self._wait_kimi_home_loaded_async(page)
                print(f"[{task.task_id}] Kimi 首页已加载；span.user-name 文本：{user_name_text!r}")
                login_status = await self._ensure_kimi_login_async(page)
                await self._wait_kimi_chat_editor_ready_async(page)

                send_result = await self.send_kimi_message_async(page, text, model_keyword)
                send_result.update(
                    {
                        "task_id": task.task_id,
                        "title": await page.title(),
                        "login_status": login_status["status_text"],
                        "user_name": login_status["user_name"],
                    }
                )
                print(f"[{task.task_id}] 已点击发送；当前页面地址：{send_result['url']}")
                return send_result
            except Exception as exc:
                print(f"[{task.task_id}] 发送流程失败：{type(exc).__name__}: {exc}")
                if attempt == self.max_retries - 1:
                    return {"status": False, "task_id": task.task_id, "msg": str(exc)}
                if page is not None and not page.is_closed():
                    await page.close()
                await asyncio.sleep(2)
            finally:
                if page is not None and not page.is_closed() and not KIMI_KEEP_BROWSER_OPEN_AFTER_SEND:
                    await page.close()

        return {"status": False, "task_id": task.task_id, "msg": "未知错误"}

    async def close(self) -> None:
        """关闭浏览器上下文和 Playwright。"""
        if self.context is not None:
            await self.context.close()
            self.context = None
        if self.playwright is not None:
            await self.playwright.stop()
            self.playwright = None

    async def __aenter__(self):
        await self._ensure_context_async()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _ = exc_type, exc_val, exc_tb
        await self.close()


def send_kimi_text(
    text: str,
    model_keyword: str = KIMI_DEFAULT_MODEL_KEYWORD,
    user_data_dir: str = KIMI_USER_DATA_DIR,
    max_retries: int = KIMI_TOTAL_RETRY_TIMES,
) -> dict:
    """
    同步对外入口：发送一段文本到 Kimi。

    输入：
    - text：要写入输入框并发送的文本；
    - model_keyword：可选，模型关键字，默认“思考”；
    - user_data_dir：可选，Chrome 持久化缓存目录，默认使用 D:\chromeCache；
    - max_retries：可选，页面加载或发送流程失败后的最大重试次数，默认 3 次。

    返回：
    - 成功：dict，包含 input_text、selected_model、url；
    - 失败：dict，包含 status=False、task_id、msg。

    selected_model 等价于页面执行 document.querySelector('.model-name>.name').textContent.trim()。
    """

    async def main() -> dict:
        async with AsyncKimiScraper(user_data_dir=user_data_dir, max_retries=max_retries) as scraper:
            task = KimiTask(
                task_id="kimi-send-1",
                payload={"text": text, "model_keyword": model_keyword},
            )
            result = await scraper.open_kimi_page_and_send_async(task)
            if not result.get("status", True):
                return result
            return {
                "input_text": result.get("input_text", ""),
                "selected_model": result.get("selected_model", ""),
                "url": result.get("url", ""),
            }

    return asyncio.run(main())


def send_kimi_texts(
    texts: list[str],
    max_concurrency: int = KIMI_MAX_CONCURRENCY,
    model_keyword: str = KIMI_DEFAULT_MODEL_KEYWORD,
) -> list[dict]:
    """
    同步对外入口：并发发送多段文本到 Kimi。

    一个浏览器，多个标签页，每个标签页独立执行发送流程。
    任务内部是否主动关闭标签页由 KIMI_KEEP_BROWSER_OPEN_AFTER_SEND 控制；函数结束时会统一关闭浏览器上下文。

    输入：
    - texts：要发送的文本列表；
    - max_concurrency：最大并发标签页数，默认 3；
    - model_keyword：模型关键字，默认"思考"。

    返回：
    - 成功：每条文本对应一个 dict，包含 input_text、selected_model、url；
    - 失败：对应位置返回 dict，包含 status=False、task_id、msg。
    """

    async def main() -> list[dict]:
        async with AsyncKimiScraper(user_data_dir=KIMI_USER_DATA_DIR, max_retries=KIMI_TOTAL_RETRY_TIMES) as scraper:
            semaphore = asyncio.Semaphore(max_concurrency)

            async def send_one(index: int, text: str) -> dict:
                async with semaphore:
                    task = KimiTask(
                        task_id=f"kimi-send-{index + 1}",
                        payload={"text": text, "model_keyword": model_keyword},
                    )
                    result = await scraper.open_kimi_page_and_send_async(task)
                    if not result.get("status", True):
                        return result
                    return {
                        "input_text": result.get("input_text", ""),
                        "selected_model": result.get("selected_model", ""),
                        "url": result.get("url", ""),
                    }

            return await asyncio.gather(*(send_one(i, t) for i, t in enumerate(texts)))

    return asyncio.run(main())


if __name__ == "__main__":
    # 单条发送示例
    result = send_kimi_text("你好 Kimi，这是单条发送示例")
    print("单条发送结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 并发发送示例（取消注释即可运行）
    # results = send_kimi_texts(
    #     texts=["第一条示例消息", "第二条示例消息", "第三条示例消息"],
    #     max_concurrency=2,
    # )
    # print("并发发送结果：")
    # print(json.dumps(results, ensure_ascii=False, indent=2))
