# Kimi 页面异步操作框架

***🌱温馨提示***
 - 本项目可作为参考，后续可以按相同的方式进行其他 LLM 的拓展，逻辑思路都是一样的。
 例如：[千问](https://www.qianwen.com/)、[豆包](https://www.doubao.com/chat/) 等。


本项目用于通过 Playwright 自动打开 Kimi 页面，复用本机 Chrome 登录态/缓存，向 Kimi 输入文本、选择模型并点击发送。

目标站点：<https://www.kimi.com/>

## 功能概览

- 使用持久化 Chrome 上下文，共享登录态和缓存。
- 默认缓存目录：`D:\chromeCache`。
- 支持未登录时自动打开登录入口，并等待人工完成登录。
- 支持单条文本发送。
- 支持多条文本并发发送，每条任务使用独立标签页。
- 默认使用可视化 Chrome，方便人工检查页面状态。

## 环境依赖

```bash
pip install playwright
playwright install chromium
```

如果代码中使用 `channel="chrome"`，请确保本机已安装 Google Chrome。

## 文件说明

```text
kimi_chat_starter.py         主程序，对外提供 Python 调用入口
kimi_input_test_cases.js      可选：Kimi 输入框手动验证脚本
kimi_select_model_test.js     可选：Kimi 模型选择手动验证脚本
kimi_click_send_test.js       可选：Kimi 发送按钮手动验证脚本
```

业务对接时通常只需要引用 `kimi_chat_starter.py`。

## 对外业务入口

严格来说，对外业务入口主要是 2 个：

1. `send_kimi_text(...)`：单条发送入口。
2. `send_kimi_texts(...)`：多条并发发送入口。

另有 `kimi_wait_ms(...)` 是内部辅助函数，不建议作为业务接口使用。

---

## 1. 单条发送：`send_kimi_text`

### 函数签名

```python
def send_kimi_text(
    text: str,
    model_keyword: str = "思考",
    user_data_dir: str = r"D:\chromeCache",
    max_retries: int = 3,
) -> dict:
    ...
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `text` | `str` | 必填 | 要写入 Kimi 输入框并发送的文本。 |
| `model_keyword` | `str` | `"思考"` | 模型关键字。脚本会选择第一个名称包含该关键字的模型。 |
| `user_data_dir` | `str` | `D:\chromeCache` | Chrome 持久化缓存目录，用于复用登录态。 |
| `max_retries` | `int` | `3` | 页面加载或发送流程失败后的最大重试次数。 |

### 调用示例

```python
from kimi_chat_starter import send_kimi_text

result = send_kimi_text("你好 Kimi，请帮我总结这段内容。")
print(result)
```

### 成功返回

```python
{
    "input_text": "你好 Kimi，请帮我总结这段内容。",
    "selected_model": "思考模型名称",
    "url": "https://www.kimi.com/..."
}
```

### 失败返回

```python
{
    "status": False,
    "task_id": "kimi-send-1",
    "msg": "错误信息"
}
```

---

## 2. 多条并发发送：`send_kimi_texts`

### 函数签名

```python
def send_kimi_texts(
    texts: list[str],
    max_concurrency: int = 3,
    model_keyword: str = "思考",
    user_data_dir: str = r"D:\chromeCache",
    max_retries: int = 3,
) -> list[dict]:
    ...
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `texts` | `list[str]` | 必填 | 要发送的文本列表。 |
| `max_concurrency` | `int` | `3` | 最大并发标签页数。 |
| `model_keyword` | `str` | `"思考"` | 模型关键字。每条任务都会按该关键字选择模型。 |
| `user_data_dir` | `str` | `D:\chromeCache` | Chrome 持久化缓存目录，用于复用登录态。 |
| `max_retries` | `int` | `3` | 页面加载或发送流程失败后的最大重试次数。 |

### 调用示例

```python
from kimi_chat_starter import send_kimi_texts

results = send_kimi_texts(
    texts=["第一条", "第二条", "第三条"],
    max_concurrency=2,
)
print(results)
```

### 成功返回

```python
[
    {
        "input_text": "第一条",
        "selected_model": "思考模型名称",
        "url": "https://www.kimi.com/..."
    },
    {
        "input_text": "第二条",
        "selected_model": "思考模型名称",
        "url": "https://www.kimi.com/..."
    }
]
```

如果某条任务失败，该位置会返回：

```python
{
    "status": False,
    "task_id": "kimi-send-2",
    "msg": "错误信息"
}
```

## 登录与缓存说明

脚本会使用 `D:\chromeCache` 作为 Chrome 持久化用户目录。

首次运行时如果 Kimi 未登录，脚本会：

1. 打开 Kimi 页面；
2. 点击页面上的登录入口；
3. 等待用户在 Chrome 窗口中人工完成登录；
4. 登录成功后继续执行发送流程。

后续运行会复用缓存目录中的登录态，通常不需要重复登录。

> 安全提醒：请勿将 Chrome 用户数据目录、登录缓存、cookie、`.env` 文件或任何包含密钥、令牌、账号信息的文件提交到公开仓库。

## 注意事项

- 运行时会打开真实 Chrome 窗口，不是纯后台模式。
- Kimi 页面结构如果调整，选择器相关逻辑可能需要同步维护。
- 并发发送时会打开多个标签页，建议根据机器性能和账号限制控制 `max_concurrency`。
- 返回的 `url` 是点击发送后的当前页面地址，可用于后续追踪或人工检查。
