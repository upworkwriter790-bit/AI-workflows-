# telynx voice agent

Workspace for voice-agent work built on the **Telnyx** plugin marketplace
(<https://github.com/team-telnyx/ai>).

## What was added

The marketplace is registered for this project in [`../.claude/settings.json`](../.claude/settings.json):

```json
{
  "extraKnownMarketplaces": {
    "telnyx": { "source": { "source": "github", "repo": "team-telnyx/ai" } }
  },
  "enabledPlugins": { "telnyx-voice@telnyx": true }
}
```

Claude Code clones the marketplace itself on session start, so the repo is
referenced rather than vendored into this project.

Equivalent interactive commands:

```
/plugin marketplace add team-telnyx/ai
/plugin install telnyx-voice@telnyx
```

## Marketplace contents

`telnyx` marketplace v0.4.0 — 11 plugins:

| Plugin | Covers |
| --- | --- |
| `telnyx-voice` | Call control, DTMF, recording, noise suppression, AMD, deepfake detection, number masking, SIPREC, streaming |
| `telnyx-ai` | LLM inference, chat completions, embeddings, AI assistants, Meeting Bot, conversation insights |
| `telnyx-tts` | Text-to-speech (Telnyx, AWS, Azure, ElevenLabs, MiniMax, Resemble, Rime, xAI) |
| `telnyx-stt` | Speech-to-text via an OpenAI-compatible endpoint |
| `telnyx-messaging` | SMS/MMS send, schedule, group MMS, delivery webhooks, opt-out |
| `telnyx-whatsapp` | WhatsApp Business API — messages, templates, WABAs, numbers |
| `telnyx-email` | Transactional email, inboxes, sending domains, suppressions |
| `telnyx-verify` | Phone verification (2FA OTP) over SMS, call, flash call |
| `telnyx-numbers` | Number search, ordering, and management |
| `telnyx-webrtc` | WebRTC clients and credentials |
| `telnyx-platform` | Platform/account services |

Only `telnyx-voice` is enabled here. To add more, set them in
`../.claude/settings.json` under `enabledPlugins` (e.g. `"telnyx-tts@telnyx": true`)
or run `/plugin install <name>@telnyx`.

## What `telnyx-voice` brings

- **37 skills** — the Voice API across curl, Go, Java, JavaScript, Python and Ruby,
  in five tracks: base, `advanced`, `conferencing`, `gather`, `media`, `streaming`,
  plus `telnyx-ai-outbound-voice-python` for outbound AI voice calls.
- **1 agent** — `contact-center-developer`.
- **1 script** — `telnyx-curl.sh`.

## Telnyx MCP server (optional)

The upstream repo also ships an MCP server definition. To use it, add to your
MCP config (this project's `.mcp.json`, copied from `.mcp.json.example`):

```json
{
  "mcpServers": {
    "telnyx": {
      "type": "http",
      "url": "https://api.telnyx.com/v2/mcp"
    }
  }
}
```

Authentication uses a Telnyx API key — keep it in the environment
(`TELNYX_API_KEY`), never committed to this repo.

## Notes

- The folder name keeps the spelling requested (`telynx`); the vendor spells it
  **Telnyx**. Rename this folder if you want them to match.
- Upstream is MIT licensed.
