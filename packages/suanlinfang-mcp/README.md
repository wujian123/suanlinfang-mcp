# suanlinfang-mcp

算邻坊（[suanlinfang.cn](https://suanlinfang.cn)）AI 能力的 MCP Server：文生图/图生图、语音转文字、文字转语音、PDF 文档识别，共 12 个工具，stdio / Streamable HTTP 双形态。

## 快速开始（本地 stdio）

```bash
pip install suanlinfang-mcp
export SUANLINFANG_API_KEY=nk-xxxx        # 控制台创建：https://suanlinfang.cn/consume-web/api-keys.html
suanlinfang-mcp
```

Key 在 [API Key 管理页](https://suanlinfang.cn/consume-web/api-keys.html) 创建，新用户注册赠 ¥10 体验金。

Claude Desktop / Cursor 配置（`mcpServers`）：

```json
{
  "mcpServers": {
    "suanlinfang": {
      "command": "suanlinfang-mcp",
      "env": { "SUANLINFANG_API_KEY": "nk-xxxx" }
    }
  }
}
```

免安装方式（uv 自动拉包隔离运行）：

```json
{
  "mcpServers": {
    "suanlinfang": {
      "command": "uvx",
      "args": ["suanlinfang-mcp"],
      "env": { "SUANLINFANG_API_KEY": "nk-xxxx" }
    }
  }
}
```

## 远程形态（免安装）

已提供常驻 Streamable HTTP 端点，支持远程 MCP 的客户端直接登记：

```json
{
  "mcpServers": {
    "suanlinfang": {
      "url": "https://suanlinfang.cn/mcp",
      "headers": { "X-SLF-Api-Key": "nk-xxxx" }
    }
  }
}
```

自建 HTTP 形态：`python -m suanlinfang_mcp.entry_http`（监听 `127.0.0.1:8090`，端口用 `SUANLINFANG_MCP_PORT` 覆盖；容器/函数计算环境注入 `PORT` 时自动绑 `0.0.0.0` 该端口。HTTP 形态下每请求优先读请求头 `X-SLF-Api-Key` / `Authorization: Bearer`）。

## 工具清单（12 个）

**IMAGE 文生图/图生图**（按张计价，分模型档位）
- `generate_image`：一次调用出图（默认最多等 120 秒）——只传 prompt 即文生图，再传 `init_image_url` 即图生图；model 留空自动选（文生图=flux2-klein、图生图=qwen-image-edit-2511）
- `get_image_task`：等待超时降级后的续查（任务不丢失）
- `list_image_models`：在线模型与实时牌价

**STT 语音转文字**（约 0.5 元/小时，按实际时长）
- `transcribe_audio`：短音频同步（≤3 分钟/20MB，公网 URL；热词 hotwords、语种自动检测）
- `submit_transcription_task` / `get_transcription_task`：长音频任务（最长 2 小时/500MB，自动 180 秒切段拼接全文）

**TTS 文字转语音**（约 2 元/万字符）
- `synthesize_speech`：短文本同步（≤1000 字符，返回 1 小时有效的下载链接）
- `submit_speech_task` / `get_speech_task`：长文本任务（≤20 万字，500 字切块拼接）
- `list_tts_voices`：21 种音色清单

**OCR 文档识别**（约 0.5~1.5 分/页）
- `submit_document_task` / `get_document_task`：整本扫描 PDF 任务（≤200MB/500 页，标准/精准双档位，精准档支持自定义 prompt）——单张图片识别 agent 自带视觉即可，本服务只做 agent 吃不下的整本文档

异步任务统一三步：`submit → 轮询 get（生图 5~10 秒、音文 10~30 秒一次，看 doneUnits/totalUnits 进度）→ 终态取结果`，终态保留 72 小时。所有产品失败不计费。

## 环境变量

| 变量 | 作用 | 默认 |
|---|---|---|
| `SUANLINFANG_API_KEY` | API Key（stdio 形态鉴权来源） | — |
| `SUANLINFANG_BASE_URL` | API 地址覆盖 | `https://suanlinfang.cn/v1` |
| `SUANLINFANG_MCP_PORT` | HTTP 形态监听端口 | 8090 |

新用户注册即赠 ¥10 体验金：[suanlinfang.cn](https://suanlinfang.cn)
