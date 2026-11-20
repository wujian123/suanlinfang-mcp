# suanlinfang-sdk

算邻坊（suanlinfang.cn）开放 API 的 Python 客户端，覆盖四条产品线：

| 产品 | 能力 | 计费口径 |
|---|---|---|
| IMAGE 生图 | 文生图 + 图生图（`generate_image` 一次调用：默认模型解析 → 参考图直传 → 提交 → 原地轮询出图） | 按张计价（分模型档位） |
| STT 语音识别 | 短音频同步转写 + 2 小时长音频异步任务（22 种中文方言自动识别、热词纠错） | 约 0.5 元/小时，按实际时长 |
| TTS 语音合成 | 21 种音色、短文本同步 + 20 万字长文本异步任务（wav/mp3） | 约 2 元/万字符 |
| OCR 文字识别 | 单图同步（标准/精准双档位、精准档支持自定义 prompt）+ 500 页 PDF 异步任务 | 约 0.5~1.5 分/页 |

## 安装

```bash
pip install suanlinfang-sdk
```

## 快速开始

```python
from suanlinfang import SuanlinfangClient

client = SuanlinfangClient(api_key="nk-xxxx")   # 控制台创建：https://suanlinfang.cn/consume-web/api-keys.html

# 语音转文字（≤3 分钟短音频，公网 URL）
result = client.stt.transcribe_url("https://example.com/audio.wav")
print(result.text)

# 文生图（默认模型，一次调用等到出图；1024×1024 PNG）
result = client.image.generate_image("一只戴眼镜的橘猫在看书，手绘插画风格")
print(result.result_url)                          # 现签下载链接，1 小时内有效

# 图生图（传参考图公网 URL，默认切到编辑模型）
result = client.image.generate_image("把风衣换成白色羽绒服", init_image_url="https://example.com/ref.png")

# 文字转语音
result = client.tts.synthesize("你好，算邻坊", speaker="suwan", audio_format="mp3")
print(result.url)                                # 现签下载链接，1 小时内有效

# 图片文字识别
result = client.ocr.recognize_url("https://example.com/img.png", tier="standard")
print(result.words)
```

长音频/长文本/PDF 走异步任务三步流：`submit_task → get_task 轮询 → 终态取结果`，状态机 `queued/running/success/failed`，终态保留 72 小时。

## 配置

| 变量 | 作用 | 默认 |
|---|---|---|
| `SUANLINFANG_API_KEY` | API Key（nk- 前缀），构造参数优先于此 | — |
| `SUANLINFANG_BASE_URL` | API 地址覆盖（联调用） | `https://suanlinfang.cn/v1` |

- 新用户注册即赠 ¥10 体验金：https://suanlinfang.cn
- 错误统一为 `SuanlinfangApiError`（含 `status_code` / `code` / `request_id` / `retryable`）；5xx 自动退避重试，超时不自动重试（防重复计费）
