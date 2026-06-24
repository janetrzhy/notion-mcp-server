# Notion MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-7C3AED.svg)](https://modelcontextprotocol.io/)
[![Notion API](https://img.shields.io/badge/Notion-API-000000.svg)](https://developers.notion.com/)

**An MCP server that gives AI assistants read/write access to Notion.** This project implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) to bridge AI language models with the [Notion API](https://developers.notion.com/), enabling autonomous page management — searching, reading, writing, editing, and commenting on Notion content through natural language.

---

## Features

| Tool | Description |
|---|---|
| `search_notion(query)` | Search pages and databases |
| `read_page(page_id)` | Read full page content with block IDs |
| `append_to_page(page_id, text)` | Append a paragraph to a page |
| `create_subpage(parent, title, ...)` | Create a new subpage with optional icon/cover |
| `append_heading(page, text, level)` | Append H1/H2/H3 heading |
| `append_bullet_list(page, items)` | Append bulleted list items |
| `append_numbered_list(page, items)` | Append numbered list items |
| `append_todo(page, items, checked)` | Append to-do items |
| `append_quote(page, text)` | Append a quote block |
| `append_callout(page, text, emoji)` | Append a callout/highlight block |
| `append_code(page, code, lang)` | Append a code block |
| `append_divider(page)` | Append a divider |
| `append_image(page, url)` | Append an image from URL |
| `append_bookmark(page, url)` | Append a bookmark card |
| `list_comments(block_id)` | List comments on a page/block |
| `create_comment(text, page_id, ...)` | Post a comment or reply to a discussion |
| `update_page(page_id, title, ...)` | Update page title, icon, cover, or archive |
| `update_block_text(block_id, text)` | Update any text-based block content |
| `delete_block(block_id)` | Delete (archive) a block |

---

## Architecture

```
┌────────────┐     MCP Protocol      ┌──────────────┐     Notion API     ┌──────────┐
│   AI       │ ◄──────────────────►  │   MCP Server  │ ◄──────────────►  │  Notion  │
│  Assistant  │     streamable-http   │  (server.py)  │   notion-client   │   Cloud  │
│ (Claude,etc)│                      │  :3002        │                   │          │
└────────────┘                       └──────┬───────┘                   └──────────┘
                                            │
                                     (Deployed on Render)
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- A [Notion Integration](https://www.notion.so/profile/integrations) token
- The integration must be **connected** to the pages you want to manage

### Installation

```bash
# Clone the repo
git clone https://github.com/your-username/notion-mcp-server.git
cd notion-mcp-server

# Install Python dependencies
pip install -r requirements.txt
```

### Run Locally

```bash
export NOTION_TOKEN=ntn_xxxxxxxxxxxx
python notion_renderserver.py
```

The server starts on `http://0.0.0.0:3002` using the `streamable-http` transport. Configure your MCP client to connect to this endpoint with the path `/sse`.

Example MCP client configuration:

```json
{
  "mcpServers": {
    "notion": {
      "url": "http://localhost:3002/sse"
    }
  }
}
```

---

## Deployment

### Deploy to Render

This repo includes a [`render.yaml`](render.yaml) for one-click deployment on Render:

1. Fork or push this repo to GitHub
2. On [Render Dashboard](https://dashboard.render.com/), click **New +** → **Blueprint**
3. Connect your repository
4. Set the `NOTION_TOKEN` environment variable as a secret

Render automatically assigns a public URL. Use that URL with `/sse` appended in your MCP client.

The server listens on the port provided by Render's `PORT` environment variable (falls back to `3002` locally).

---

## API Reference

### Search & Read

- **`search_notion(query: str = "")`** — Searches all accessible pages and databases. Returns title and ID per result. Omit or pass an empty string to list everything the integration can see.
- **`read_page(page_id: str)`** — Reads page content block by block. Each output line is prefixed with `<block_id>` so you can later edit or delete specific blocks.

### Write

- **`append_to_page(page_id, text)`** — Appends a simple paragraph.
- **`create_subpage(parent_page_id, title, icon_emoji="", cover_url="")`** — Creates a child page. Both `icon_emoji` and `cover_url` are optional.

### Rich Content

Each of these appends a specific block type to a page:

| Tool | Notion Block Type |
|---|---|
| `append_heading(page, text, level=1)` | `heading_1` / `heading_2` / `heading_3` |
| `append_bullet_list(page, items)` | `bulleted_list_item` |
| `append_numbered_list(page, items)` | `numbered_list_item` |
| `append_todo(page, items, checked)` | `to_do` |
| `append_quote(page, text)` | `quote` |
| `append_callout(page, text, emoji)` | `callout` |
| `append_code(page, code, lang)` | `code` |
| `append_divider(page)` | `divider` |
| `append_image(page, url)` | `image` (external) |
| `append_bookmark(page, url)` | `bookmark` |

### Comments

- **`list_comments(block_id)`** — Lists all comments on the given page or block.
- **`create_comment(text, page_id, discussion_id)`** — Posts a new top-level comment on a page, or replies to an existing discussion thread.

### Edit & Delete

- **`update_page(page_id, title, icon_emoji, cover_url, archived)`** — Updates page metadata. Empty fields are left as-is. Set `archived=True` to move to trash.
- **`update_block_text(block_id, text)`** — Replaces the text content of any supported block type.
- **`delete_block(block_id)`** — Archives (soft-deletes) a block.

---

## Use Cases

- **AI-powered note-taking** — have an AI read, summarize, and organize your Notion workspace
- **Automated documentation** — create pages, structure headings, and populate content programmatically
- **Meeting notes assistant** — an AI attends a conversation and writes structured notes to Notion
- **Content migration** — batch-import content from other sources into Notion
- **Knowledge base management** — search, update, and maintain a Notion-powered knowledge base

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Protocol** | [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) |
| **Python Framework** | [FastMCP](https://github.com/jlowin/fastmcp) |
| **Notion Client** | [notion-client](https://github.com/ramnes/notion-sdk-py) (official SDK) |
| **Deployment** | [Render](https://render.com/) (via `render.yaml`) |

---

## Project Structure

```
notion-mcp-server/
├── notion_renderserver.py       # MCP server entry point
├── requirements.txt             # Python dependencies
├── render.yaml                  # Render deployment blueprint
├── .gitignore
└── README.md
```

---

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-idea`)
3. Commit your changes (`git commit -m 'Add amazing idea'`)
4. Push to the branch (`git push origin feature/amazing-idea`)
5. Open a Pull Request

---

## License

[MIT](LICENSE) © 2025

---

## Why This Exists

Large Language Models excel at understanding and generating text, but they have no direct access to your personal knowledge base locked inside Notion. This server bridges that gap — it gives AI assistants structured read/write access to your workspace through the standard MCP protocol, enabling them to search, retrieve, organize, and update your notes on your behalf.

Built for the [Model Context Protocol](https://modelcontextprotocol.io/) ecosystem.
