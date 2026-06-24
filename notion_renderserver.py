"""
Notion MCP Server

A Model Context Protocol (MCP) server that bridges AI assistants with the
Notion API, enabling page search, content reading, block creation, editing,
and commenting — all through natural language.
"""

import os
from mcp.server.fastmcp import FastMCP
from notion_client import Client

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
if not NOTION_TOKEN:
    raise ValueError("NOTION_TOKEN environment variable is required")

notion = Client(auth=NOTION_TOKEN)

# Render assigns the port via the PORT environment variable
port = int(os.environ.get("PORT", 3002))
mcp = FastMCP("Notion MCP Server", host="0.0.0.0", port=port)


# ---------- Helpers ----------

def _rt(text: str):
    """Build a Notion rich_text array from a plain string."""
    return [{"type": "text", "text": {"content": text}}]


def _paragraph(text: str):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": _rt(text)}}


# ---------- Search, Read, Append ----------

@mcp.tool()
async def search_notion(query: str = "") -> str:
    """Search Notion pages. Returns all accessible pages when query is empty."""
    results = notion.search(query=query, page_size=20)
    pages = []
    for item in results.get("results", []):
        title = ""
        if item["object"] == "page":
            props = item.get("properties", {})
            for prop in props.values():
                if prop.get("type") == "title":
                    title_parts = prop.get("title", [])
                    title = "".join([t.get("plain_text", "") for t in title_parts])
                    break
            if not title:
                title = "Untitled"
            pages.append(f"[{title}] id={item['id']}")
        elif item["object"] == "database":
            db_title = item.get("title", [])
            title = "".join([t.get("plain_text", "") for t in db_title])
            pages.append(f"[DB: {title}] id={item['id']}")
    return "\n".join(pages) if pages else "No results found"


@mcp.tool()
async def read_page(page_id: str) -> str:
    """Read full page content. Each line is prefixed with <block_id> for editing/deletion."""
    blocks = notion.blocks.children.list(block_id=page_id, page_size=100)
    lines = []
    for block in blocks.get("results", []):
        btype = block.get("type", "")
        data = block.get(btype, {})
        bid = block["id"]
        prefix = f"<{bid}>"
        if "rich_text" in data:
            text = "".join([t.get("plain_text", "") for t in data["rich_text"]])
            if btype.startswith("heading"):
                text = f"{'#' * int(btype[-1])} {text}"
            elif btype == "bulleted_list_item":
                text = f"- {text}"
            elif btype == "numbered_list_item":
                text = f"1. {text}"
            elif btype == "to_do":
                checked = data.get("checked", False)
                text = f"[{'x' if checked else ' '}] {text}"
            elif btype == "quote":
                text = f"> {text}"
            elif btype == "callout":
                emoji = (data.get("icon") or {}).get("emoji", "💬")
                text = f"{emoji} {text}"
            elif btype == "code":
                lang = data.get("language", "")
                text = f"```{lang}\n{text}\n```"
            lines.append(f"{prefix} {text}")
        elif btype == "divider":
            lines.append(f"{prefix} ---")
        elif btype == "image":
            url = ""
            if data.get("type") == "external":
                url = data.get("external", {}).get("url", "")
            elif data.get("type") == "file":
                url = data.get("file", {}).get("url", "")
            lines.append(f"{prefix} [Image] {url}")
        elif btype == "bookmark":
            lines.append(f"{prefix} [Bookmark] {data.get('url', '')}")
        elif btype == "child_page":
            lines.append(f"{prefix} [Subpage: {data.get('title', 'Untitled')}]")
        elif btype == "child_database":
            lines.append(f"{prefix} [Sub-database: {data.get('title', 'Untitled')}]")
    return "\n".join(lines) if lines else "(Page is empty or content could not be read)"


@mcp.tool()
async def append_to_page(page_id: str, text: str) -> str:
    """Append a plain text paragraph to the end of a Notion page."""
    notion.blocks.children.append(block_id=page_id, children=[_paragraph(text)])
    return f"Appended content to page {page_id}"


# ---------- Create Subpages ----------

@mcp.tool()
async def create_subpage(parent_page_id: str, title: str,
                         icon_emoji: str = "", cover_url: str = "") -> str:
    """Create a subpage under a parent page, with optional emoji icon and cover image."""
    payload = {
        "parent": {"page_id": parent_page_id},
        "properties": {"title": {"title": _rt(title)}},
    }
    if icon_emoji:
        payload["icon"] = {"type": "emoji", "emoji": icon_emoji}
    if cover_url:
        payload["cover"] = {"type": "external", "external": {"url": cover_url}}
    page = notion.pages.create(**payload)
    return f"Created subpage [{title}] id={page['id']}"


# ---------- Rich Content Blocks ----------

@mcp.tool()
async def append_heading(page_id: str, text: str, level: int = 1) -> str:
    """Append a heading block. Level: 1, 2, or 3."""
    level = max(1, min(3, level))
    btype = f"heading_{level}"
    block = {"object": "block", "type": btype, btype: {"rich_text": _rt(text)}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return f"Appended H{level} heading"


@mcp.tool()
async def append_bullet_list(page_id: str, items: list[str]) -> str:
    """Append bulleted list items (multiple at once)."""
    children = [
        {"object": "block", "type": "bulleted_list_item",
         "bulleted_list_item": {"rich_text": _rt(t)}}
        for t in items
    ]
    notion.blocks.children.append(block_id=page_id, children=children)
    return f"Appended {len(children)} bullet list item(s)"


@mcp.tool()
async def append_numbered_list(page_id: str, items: list[str]) -> str:
    """Append numbered list items (multiple at once)."""
    children = [
        {"object": "block", "type": "numbered_list_item",
         "numbered_list_item": {"rich_text": _rt(t)}}
        for t in items
    ]
    notion.blocks.children.append(block_id=page_id, children=children)
    return f"Appended {len(children)} numbered list item(s)"


@mcp.tool()
async def append_todo(page_id: str, items: list[str], checked: bool = False) -> str:
    """Append to-do blocks (multiple at once), with optional default check state."""
    children = [
        {"object": "block", "type": "to_do",
         "to_do": {"rich_text": _rt(t), "checked": checked}}
        for t in items
    ]
    notion.blocks.children.append(block_id=page_id, children=children)
    return f"Appended {len(children)} to-do item(s)"


@mcp.tool()
async def append_quote(page_id: str, text: str) -> str:
    """Append a quote block."""
    block = {"object": "block", "type": "quote",
             "quote": {"rich_text": _rt(text)}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "Appended quote"


@mcp.tool()
async def append_callout(page_id: str, text: str, emoji: str = "💡") -> str:
    """Append a callout/highlight block with a custom emoji icon."""
    block = {"object": "block", "type": "callout",
             "callout": {"rich_text": _rt(text),
                         "icon": {"type": "emoji", "emoji": emoji}}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "Appended callout"


@mcp.tool()
async def append_code(page_id: str, code: str, language: str = "plain text") -> str:
    """Append a code block. Language examples: python, javascript, typescript, shell, json, markdown."""
    block = {"object": "block", "type": "code",
             "code": {"rich_text": _rt(code), "language": language}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "Appended code block"


@mcp.tool()
async def append_divider(page_id: str) -> str:
    """Append a divider line."""
    block = {"object": "block", "type": "divider", "divider": {}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "Appended divider"


@mcp.tool()
async def append_image(page_id: str, image_url: str) -> str:
    """Append an image from an external URL."""
    block = {"object": "block", "type": "image",
             "image": {"type": "external", "external": {"url": image_url}}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "Appended image"


@mcp.tool()
async def append_bookmark(page_id: str, url: str) -> str:
    """Append a bookmark card with a link."""
    block = {"object": "block", "type": "bookmark", "bookmark": {"url": url}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "Appended bookmark"


# ---------- Comments ----------

@mcp.tool()
async def list_comments(block_id: str) -> str:
    """List comments on a page or block."""
    res = notion.comments.list(block_id=block_id)
    items = res.get("results", [])
    if not items:
        return "(No comments)"
    lines = []
    for c in items:
        text = "".join([t.get("plain_text", "") for t in c.get("rich_text", [])])
        user = c.get("created_by", {}).get("id", "")
        ts = c.get("created_time", "")
        disc = c.get("discussion_id", "")
        lines.append(f"[{ts}] {user}: {text} (id={c['id']} discussion={disc})")
    return "\n".join(lines)


@mcp.tool()
async def create_comment(text: str, page_id: str = "", discussion_id: str = "") -> str:
    """Post a comment on a page, or reply to an existing discussion thread."""
    if discussion_id:
        res = notion.comments.create(discussion_id=discussion_id, rich_text=_rt(text))
    elif page_id:
        res = notion.comments.create(parent={"page_id": page_id}, rich_text=_rt(text))
    else:
        return "Provide either page_id or discussion_id"
    return f"Posted comment id={res['id']}"


# ---------- Page / Block Editing & Deletion ----------

@mcp.tool()
async def update_page(page_id: str, title: str = "",
                      icon_emoji: str = "", cover_url: str = "",
                      archived: bool = False) -> str:
    """Update a page's title, icon, cover, or archive status. Empty fields are left unchanged."""
    payload = {}
    if title:
        payload["properties"] = {"title": {"title": _rt(title)}}
    if icon_emoji:
        payload["icon"] = {"type": "emoji", "emoji": icon_emoji}
    if cover_url:
        payload["cover"] = {"type": "external", "external": {"url": cover_url}}
    if archived:
        payload["archived"] = True
    if not payload:
        return "No fields to update"
    notion.pages.update(page_id=page_id, **payload)
    return f"Updated page {page_id}"


@mcp.tool()
async def update_block_text(block_id: str, text: str) -> str:
    """Update the text content of a text-based block (paragraph, heading, list, to-do, quote, callout, code)."""
    block = notion.blocks.retrieve(block_id=block_id)
    btype = block.get("type", "")
    supported = {"paragraph", "heading_1", "heading_2", "heading_3",
                 "bulleted_list_item", "numbered_list_item", "to_do",
                 "quote", "callout", "code"}
    if btype not in supported:
        return f"Block type '{btype}' does not support text updates"
    body = dict(block.get(btype, {}))
    body["rich_text"] = _rt(text)
    notion.blocks.update(block_id=block_id, **{btype: body})
    return f"Updated block {block_id}"


@mcp.tool()
async def delete_block(block_id: str) -> str:
    """Delete (archive) a block."""
    notion.blocks.delete(block_id=block_id)
    return f"Deleted block {block_id}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
