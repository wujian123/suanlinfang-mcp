# SuanLinFang MCP Server — Pay-as-you-go AI capabilities

Official website: **[https://suanlinfang.cn](https://suanlinfang.cn)** — create an API key at [API Key Management](https://suanlinfang.cn/consume-web/api-keys.html) (new accounts get a free trial credit).

Remote MCP server with **11 tools** in four capability families, Chinese-optimized, pay-as-you-go (failed calls are never billed):

| Family | Tools | Highlights |
|---|---|---|
| Speech-to-Text (STT) | `transcribe_audio`, `submit_transcription_task`, `get_transcription_task` | ≤2h audio, hot-word correction, auto detection for Mandarin/English + 22 Chinese dialects |
| Text-to-Speech (TTS) | `synthesize_speech`, `estimate_tts_cost`, `submit_speech_task`, `get_speech_task`, `list_tts_voices` | 21 voices, ≤200k chars per task, wav/mp3 |
| OCR | `recognize_image`, `submit_document_task`, `get_document_task` | standard/accurate tiers, custom prompt (accurate tier), PDF ≤500 pages |
| Decision | `decide` | typed judgments with calibrated confidence — choice / yes-no / score questions |

## Connect (remote, recommended)

Works with any MCP client that supports Streamable HTTP:

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

Claude Code one-liner:

```bash
claude mcp add --transport http suanlinfang https://suanlinfang.cn/mcp \
  --header "X-SLF-Api-Key: nk-YOUR_API_KEY"
```

Browse the tool catalog without a key: the endpoint answers `initialize` and `tools/list` publicly — tool **calls** require your key.

## Install (local stdio)

Published on PyPI as [`suanlinfang-mcp`](https://pypi.org/project/suanlinfang-mcp/):

```bash
pip install suanlinfang-mcp
export SUANLINFANG_API_KEY="nk-YOUR_API_KEY"
suanlinfang-mcp        # stdio entry for Claude Desktop / Cursor / etc.
```

or run without installing: `uvx suanlinfang-mcp`

Environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `SUANLINFANG_API_KEY` | your API key (`nk-` prefix) for stdio/local use | required for stdio |
| `SUANLINFANG_BASE_URL` | API base override | `https://suanlinfang.cn/v1` |
| `SUANLINFANG_MCP_PORT` | listen port for the HTTP entry | `8090` |

The Python SDK lives in `packages/suanlinfang-sdk/` — a dependency-free REST client (`pip install suanlinfang-sdk`) you can use without MCP.

## Get an API key

1. Register at [suanlinfang.cn](https://suanlinfang.cn) (new accounts get trial credit)
2. Console → [API Key Management](https://suanlinfang.cn/consume-web/api-keys.html) → create key (`nk-` prefix)
3. Put the key in the `X-SLF-Api-Key` header (remote) or `SUANLINFANG_API_KEY` env (stdio)

Reference pricing: transcription ≈ ¥0.5/hour of audio, TTS ≈ ¥2/10k chars, OCR ≈ ¥0.005–0.015/page, decision ≈ ¥2/M input tokens. Failed calls are never billed.

## Docker

Docker image distribution is planned (`mcp/suanlinfang` via the Docker MCP Catalog) — see TODO.

## Development

```bash
cd mcp-server
uv sync                                  # workspace: sdk + mcp packages + dev deps
uv run pytest                            # all tests
uv run fastmcp dev packages/suanlinfang-mcp/suanlinfang_mcp/server.py   # MCP Inspector
uv run python -m suanlinfang_mcp.entry_http   # local HTTP entry (127.0.0.1:8090/mcp)
```

Repo layout:

- `packages/suanlinfang-sdk/` — REST client SDK (no MCP concepts; reusable by CLIs and other hosts)
- `packages/suanlinfang-mcp/` — MCP protocol shell exposing the 11 tools
- `server.json` — official [MCP Registry](https://registry.modelcontextprotocol.io) metadata (`cn.suanlinfang/stt-tts-ocr-decision`)

## License

[Apache-2.0](LICENSE). The MCP server is open source; the AI inference, billing and scheduling core runs server-side at suanlinfang.cn and is not part of this repo.
