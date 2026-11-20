---
name: suanlinfang
description: 算邻坊AI能力 - 文生图/图生图、语音识别、语音合成、文字识别（OCR）四类 MCP 工具的使用指引
version: 1.1.0
author: suanlinfang
license: Apache-2.0
---

# 算邻坊 AI 能力

文生图/图生图（Image）/ 语音识别（STT）/ 语音合成（TTS）/ 文字识别（OCR）四类能力，
中文场景深度优化，按量计费，失败不计费。官网与注册：[suanlinfang.cn](https://suanlinfang.cn)
（新用户注册赠 ¥10 体验金）。

## 授权与凭证

- 本 MCP 服务需要算邻坊 API Key（`nk-` 开头）：在
  [API Key 管理页](https://suanlinfang.cn/consume-web/api-keys.html)
  创建，新注册用户附赠体验金
- 远程 HTTP 形态：Key 以 `X-SLF-Api-Key` 请求头注入；本地 stdio 形态：Key 走
  `SUANLINFANG_API_KEY` 环境变量
- 授权范围：Key 仅代表算邻坊账户的 API 调用额度与计费归因，不读取用户本地数据
- 常见错误处理：
  - 401「缺少 API Key」= 凭证未配置或已失效，请检查 header / 环境变量
  - 402「余额不足」= 引导用户到算邻坊官网充值
  - 503 = 对应能力节点暂不可用（多为供给切换），稍后重试即可
- Key 可在官网随时作废重建，作废后客户端配置需同步更新

## 使用策略（重要）

- **文生图/图生图**：一个工具 `generate_image` 搞定——只传 `prompt` 即文生图，
  再传 `init_image_url`（参考图公网 URL，png/jpg/jpeg ≤10MB）即图生图（编辑指令写在 prompt 里）。
  工具内部提交任务并等待出图（默认最多 120 秒，`wait_seconds` 可调 10~300），成功直接返回
  `resultUrl`。**model 留空自动选**（文生图=flux2-klein 快而省、图生图=qwen-image-edit-2511），
  要更高质量传 `z-image-turbo`；在线模型与牌价先查 `list_image_models`
- 拿到 `resultUrl` **立即提醒用户下载转存**（现签链接 1 小时有效）；`seed` 复现同图
  （同 prompt + 同 seed 出一致结果）
- **语音转写**：音频 ≤3 分钟用 `transcribe_audio`（同步秒级）；更长（最长 2 小时）用
  `submit_transcription_task` 提交后轮询 `get_transcription_task`
- **语音合成**：文本 ≤1000 汉字用 `synthesize_speech`（同步）；更长（≤20 万字）用
  `submit_speech_task` 提交后轮询 `get_speech_task`
- 合成结果 URL 现签 1 小时有效——**拿到即提醒用户下载转存**，过期只能重合成（重复计费）
- 选音色先 `list_tts_voices` 查 code
- **热词纠错**：转写内容含专有名词（人名/品牌/术语）时把 `hotwords` 传上（逗号分隔），
  专名错字率显著下降——会议转写建议填与会人名
- **文档识别**：整本 PDF（扫描合同/书/报告，≤500 页）用 `submit_document_task` 提交后轮询
  `get_document_task`——这是 agent 视觉做不了的场景（500 页图塞不进上下文）；
  单张图片的文字识别不必用本服务，agent 自带视觉即可
- 轮询节奏：生图任务 5~10 秒间隔、音文任务 10~30 秒间隔查询一次；任务终态结果保留 72 小时
- 金额口径（参考）：生图按张计价（分模型档位，以 `list_image_models` 实时牌价为准）、
  转写约 0.5 元/小时、合成约 2 元/万字符、OCR 约 0.5~1.5 分/页

## 工具清单（12 个）

### generate_image — 文生图/图生图（一次调用出图）
参数：`prompt`（生成/编辑指令）、`model`（可选，留空自动选：文生图=flux2-klein、
图生图=qwen-image-edit-2511；更高质量传 z-image-turbo）、`init_image_url`（可选，
参考图公网 URL，传了即图生图）、`seed`（可选，复现同图）、`wait_seconds`
（可选，等待上限，默认 120，范围 10~300）。
返回：成功出 `resultUrl`（现签 1 小时，提醒用户下载转存）+ `model` + `seed`；
等待超时返回 `taskNo`，用 `get_image_task` 续查。

### get_image_task — 查询生图任务
参数：`task_no`。status：queued/running（进行中）、success（`resultUrl` 为图片现签
下载链接，链接过期后重查即换新链）、failed（`errorMsg`，不扣费）、expired。

### list_image_models — 生图模型与牌价
无参数。返回在线模型（id）与实时牌价（pricing），选 model 前先查。

### transcribe_audio — 短音频转文字（同步）
参数：`audio_url`（音频公网 URL，≤3 分钟/20MB）、`language`（可选，语种代码如 zh/en，
留空自动检测，支持普通话、英语及 22 种中文方言）、`hotwords`（可选，热词，逗号分隔）。
返回：全文纯文本 + 时长（不含时间戳）。

### submit_transcription_task — 长音频转写任务
参数：`audio_url`（≤2 小时/500MB，wav/mp3/flac/m4a/ogg/aac）、`language`、`hotwords`
（热词对全部段生效）、`file_name`（可选）。
平台按 180 秒切段逐段转写拼接全文，返回 taskNo。

### get_transcription_task — 查询转写任务
参数：`task_no`。status：queued/running（看 doneUnits/totalUnits 进度）、
success（全文文本）、failed（errorMsg）。

### synthesize_speech — 短文本转语音（同步）
参数：`text`（≤1000 字符）、`speaker`（音色 code，默认 default）、
`audio_format`（wav/mp3，默认 wav）。
返回：现签音频下载 URL + 时长。

### submit_speech_task — 长文本合成任务
参数：`text`（≤20 万字）、`speaker`、`audio_format`。
按 500 字切块合成拼接完整音频，返回 taskNo。

### get_speech_task — 查询合成任务
参数：`task_no`。success 时 resultUrl 为完整音频下载链接 + 总时长。

### list_tts_voices — 音色清单
无参数。返回全部可用音色（code/name/gender/styleTag，当前 21 个），选 speaker 前先查。

### submit_document_task — PDF 文档识别任务
参数：`document_url`（PDF 公网 URL，≤200MB/≤500 页）、`tier`（standard/accurate）、
`prompt`（可选，仅精准档，≤2000 字符，如「只提取表格金额列」）、
`file_name`（可选）。逐页识别整本，返回 taskNo。

### get_document_task — 查询文档识别任务
参数：`task_no`。success 时 resultUrl 为聚合结果下载链接。
