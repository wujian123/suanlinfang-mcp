# SuanLinFang MCP — install guide for AI agents

Install target: a remote MCP server (Streamable HTTP) exposing 12 pay-as-you-go AI tools
(AI image generation & editing, speech-to-text, text-to-speech, document OCR). Website: https://suanlinfang.cn

The user needs an API key (prefix `nk-`). Get one at
https://suanlinfang.cn/consume-web/api-keys.html (registration includes free trial credit).
Ask the user for their key; never invent one.

## Remote HTTP (preferred)

MCP clients config (JSON):

```json
{
  "mcpServers": {
    "suanlinfang": {
      "type": "streamableHttp",
      "url": "https://suanlinfang.cn/mcp",
      "headers": {
        "X-SLF-Api-Key": "nk-YOUR_API_KEY"
      }
    }
  }
}
```

Claude Code:

```bash
claude mcp add --transport http suanlinfang https://suanlinfang.cn/mcp \
  --header "X-SLF-Api-Key: nk-YOUR_API_KEY"
```

Cursor (mcp.json) uses the same `mcpServers` block with `"type": "streamableHttp"`.

## Local stdio (no public URL needed)

```bash
pip install suanlinfang-mcp
export SUANLINFANG_API_KEY="nk-YOUR_API_KEY"
suanlinfang-mcp
```

or `uvx suanlinfang-mcp` with the env var set.

## Verify

- `initialize` and `tools/list` answer without a key (public catalog)
- `list_tts_voices` is a cheap first call to confirm the key works (21 voices)
- Errors: 401 = missing/invalid key (re-check config), 402 = balance empty (top up at
  suanlinfang.cn), 503 = capability node busy (retry shortly)

## Tools (12)

Image: `generate_image` (text-to-image & image-to-image in one call — pass `prompt` alone or add
`init_image_url` as the reference image for editing; model auto-selected by default, 1024×1024 PNG,
billed per image), `get_image_task` (fallback poll if the wait times out), `list_image_models`
(live models & prices) ·
STT: `transcribe_audio` (≤3 min sync), `submit_transcription_task` / `get_transcription_task`
(≤2h, hot words via `hotwords`, 22 Chinese dialects) ·
TTS: `synthesize_speech` (≤1000 chars sync), `submit_speech_task` /
`get_speech_task` (≤200k chars), `list_tts_voices` ·
Document OCR: `submit_document_task` / `get_document_task` (full scanned PDFs ≤500 pages —
whole-document jobs too large to feed through the agent's own vision).
