---
name: suanlinfang
description: 算邻坊AI能力 - 语音识别、语音合成、文字识别（OCR）、智能决策四类 MCP 工具的使用指引
version: 1.0.0
author: suanlinfang
license: Apache-2.0
---

# 算邻坊 AI 能力

语音识别（STT）/ 语音合成（TTS）/ 文字识别（OCR）/ 智能决策四类能力，中文场景深度优化，
按量计费，失败不计费。

## 授权与凭证

- 本 MCP 服务需要算邻坊 API Key（`nk-` 开头）：在 https://suanlinfang.cn/consume-web/api-keys.html
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

- **语音转写**：音频 ≤3 分钟用 `transcribe_audio`（同步秒级）；更长（最长 2 小时）用
  `submit_transcription_task` 提交后轮询 `get_transcription_task`
- **语音合成**：文本 ≤1000 汉字用 `synthesize_speech`（同步）；更长（≤20 万字）用
  `submit_speech_task` 提交后轮询 `get_speech_task`
- 合成结果 URL 现签 1 小时有效——**拿到即提醒用户下载转存**，过期只能重合成（重复计费）
- 选音色先 `list_tts_voices` 查 code；对成本敏感先 `estimate_tts_cost`
- **热词纠错**：转写内容含专有名词（人名/品牌/术语）时把 `context` 传上（逗号分隔），
  专名错字率显著下降——会议转写建议填与会人名
- **图片识别**：单图用 `recognize_image`（standard 标准档快 / accurate 精准档适合表格、
  多栏、倾斜拍摄；精准档可用 prompt 定制如「只提取表格金额列」）；整本 PDF（≤500 页）
  用 `submit_document_task` + 轮询
- 轮询节奏：任务提交后 10~30 秒间隔查询一次；任务终态结果保留 72 小时
- 金额口径（参考）：转写约 0.5 元/小时、合成约 2 元/万字符、OCR 约 0.5~1.5 分/页、
  决策约 2 元/百万输入 token

## 工具清单（11 个）

### transcribe_audio — 短音频转文字（同步）
参数：`audio_url`（音频公网 URL，≤3 分钟/20MB）、`language`（可选，语种代码如 zh/en，
留空自动检测，支持普通话、英语及 22 种中文方言）、`context`（可选，热词，逗号分隔）。
返回：全文纯文本 + 时长（不含时间戳）。

### submit_transcription_task — 长音频转写任务
参数：`audio_url`（≤2 小时/500MB，wav/mp3/flac/m4a/ogg/aac）、`language`、`context`
（热词对全部段生效）、`file_name`（可选）。
平台按 180 秒切段逐段转写拼接全文，返回 taskNo。

### get_transcription_task — 查询转写任务
参数：`task_no`。status：queued/running（看 doneUnits/totalUnits 进度）、
success（全文文本）、failed（errorMsg）。

### synthesize_speech — 短文本转语音（同步）
参数：`text`（≤3000 UTF-8 字节约 1000 汉字）、`speaker`（音色 code，默认 default）、
`audio_format`（wav/mp3，默认 wav）。
返回：现签音频下载 URL + 时长。

### estimate_tts_cost — 估算合成成本
参数：`text`、`speaker`（可选）。返回：计费字符数与预计费用。

### submit_speech_task — 长文本合成任务
参数：`text`（≤20 万字）、`speaker`、`audio_format`。
按 500 字切块合成拼接完整音频，返回 taskNo。

### get_speech_task — 查询合成任务
参数：`task_no`。success 时 resultUrl 为完整音频下载链接 + 总时长。

### list_tts_voices — 音色清单
无参数。返回全部可用音色（code/name/gender/styleTag，当前 21 个），选 speaker 前先查。

### recognize_image — 图片文字识别（同步）
参数：`image_url`（图片公网 URL，png/jpg/webp/bmp ≤20MB）、`tier`
（standard/accurate）、`prompt`（可选，仅精准档，≤2000 字符）。
返回：逐行文本。计费按页（单图=1 页）。

### submit_document_task — PDF 文档识别任务
参数：`document_url`（PDF 公网 URL，≤200MB/≤500 页）、`tier`、`prompt`（仅精准档）、
`file_name`（可选）。逐页识别整本，返回 taskNo。

### get_document_task — 查询文档识别任务
参数：`task_no`。success 时 resultUrl 为聚合结果下载链接。

### decide — 智能决策判断
参数：`state`（业务状态描述）、`questions`（{题目id: 题目} 映射，1-32 题，
type=choice 多选一 / noul 是否判断 / score 有序等级打分）、`questions_json`
（questions 的 JSON 字符串形式，与 questions 二选一）。
返回：每题的选中项、置信度与全选项校准概率，不生成自由文本。
适用：工单分类、风控判定、质检评估等结构化判断。
