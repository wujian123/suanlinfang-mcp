# SuanLinFang MCP — install guide for AI agents

Install target: a remote MCP server (Streamable HTTP) exposing 11 pay-as-you-go AI tools
(speech-to-text, text-to-speech, OCR, typed decision-making). Website: https://suanlinfang.cn

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

## Tools (11)

STT: `transcribe_audio` (≤3 min sync), `submit_transcription_task` / `get_transcription_task`
(≤2h, hot words via `context`, 22 Chinese dialects) ·
TTS: `synthesize_speech` (≤1000 chars sync), `estimate_tts_cost`, `submit_speech_task` /
`get_speech_task` (≤200k chars), `list_tts_voices` ·
OCR: `recognize_image` (standard/accurate tiers, optional prompt), `submit_document_task` /
`get_document_task` (PDF ≤500 pages) ·
Decision: `decide` (choice/yes-no/score questions with calibrated probabilities).
