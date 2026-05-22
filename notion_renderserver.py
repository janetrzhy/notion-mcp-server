import os
from mcp.server.fastmcp import FastMCP
from notion_client import Client

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
if not NOTION_TOKEN:
    raise ValueError("缺少 NOTION_TOKEN 环境变量")

notion = Client(auth=NOTION_TOKEN)

# Render会通过PORT环境变量分配端口
port = int(os.environ.get("PORT", 3002))
mcp = FastMCP("S的手-Notion", host="0.0.0.0", port=port)


# ---------- 内部工具 ----------

def _rt(text: str):
    """构造 Notion rich_text 数组"""
    return [{"type": "text", "text": {"content": text}}]


def _paragraph(text: str):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": _rt(text)}}


# ---------- 原有：搜索、读取、追加段落 ----------

@mcp.tool()
async def search_notion(query: str = "") -> str:
    """搜索Notion页面。query为空时返回所有可访问页面"""
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
    return "\n".join(pages) if pages else "没有找到结果"


@mcp.tool()
async def read_page(page_id: str) -> str:
    """读取Notion页面的全部内容。每行前带 <block_id>，可用于后续编辑/删除"""
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
            lines.append(f"{prefix} [图片] {url}")
        elif btype == "bookmark":
            lines.append(f"{prefix} [书签] {data.get('url', '')}")
        elif btype == "child_page":
            lines.append(f"{prefix} [子页面: {data.get('title', 'Untitled')}]")
        elif btype == "child_database":
            lines.append(f"{prefix} [子数据库: {data.get('title', 'Untitled')}]")
    return "\n".join(lines) if lines else "（页面为空或内容无法读取）"


@mcp.tool()
async def append_to_page(page_id: str, text: str) -> str:
    """在Notion页面末尾追加一段普通文字段落"""
    notion.blocks.children.append(block_id=page_id, children=[_paragraph(text)])
    return f"已追加内容到页面 {page_id}"


# ---------- 创建子页面 ----------

@mcp.tool()
async def create_subpage(parent_page_id: str, title: str,
                         icon_emoji: str = "", cover_url: str = "") -> str:
    """在指定父页面下新建子页面，可选 emoji 图标与封面图 URL"""
    payload = {
        "parent": {"page_id": parent_page_id},
        "properties": {"title": {"title": _rt(title)}},
    }
    if icon_emoji:
        payload["icon"] = {"type": "emoji", "emoji": icon_emoji}
    if cover_url:
        payload["cover"] = {"type": "external", "external": {"url": cover_url}}
    page = notion.pages.create(**payload)
    return f"已创建子页面 [{title}] id={page['id']}"


# ---------- 装饰页面：富文本块 ----------

@mcp.tool()
async def append_heading(page_id: str, text: str, level: int = 1) -> str:
    """追加标题块，level 取 1/2/3"""
    level = max(1, min(3, level))
    btype = f"heading_{level}"
    block = {"object": "block", "type": btype, btype: {"rich_text": _rt(text)}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return f"已追加 H{level} 标题"


@mcp.tool()
async def append_bullet_list(page_id: str, items: list[str]) -> str:
    """追加无序列表（一次可多条）"""
    children = [
        {"object": "block", "type": "bulleted_list_item",
         "bulleted_list_item": {"rich_text": _rt(t)}}
        for t in items
    ]
    notion.blocks.children.append(block_id=page_id, children=children)
    return f"已追加 {len(children)} 条无序列表项"


@mcp.tool()
async def append_numbered_list(page_id: str, items: list[str]) -> str:
    """追加有序列表（一次可多条）"""
    children = [
        {"object": "block", "type": "numbered_list_item",
         "numbered_list_item": {"rich_text": _rt(t)}}
        for t in items
    ]
    notion.blocks.children.append(block_id=page_id, children=children)
    return f"已追加 {len(children)} 条有序列表项"


@mcp.tool()
async def append_todo(page_id: str, items: list[str], checked: bool = False) -> str:
    """追加待办块（一次可多条），可指定默认勾选状态"""
    children = [
        {"object": "block", "type": "to_do",
         "to_do": {"rich_text": _rt(t), "checked": checked}}
        for t in items
    ]
    notion.blocks.children.append(block_id=page_id, children=children)
    return f"已追加 {len(children)} 条待办"


@mcp.tool()
async def append_quote(page_id: str, text: str) -> str:
    """追加引用块"""
    block = {"object": "block", "type": "quote",
             "quote": {"rich_text": _rt(text)}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "已追加引用"


@mcp.tool()
async def append_callout(page_id: str, text: str, emoji: str = "💡") -> str:
    """追加 callout 高亮块，可指定 emoji 图标"""
    block = {"object": "block", "type": "callout",
             "callout": {"rich_text": _rt(text),
                         "icon": {"type": "emoji", "emoji": emoji}}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "已追加 callout"


@mcp.tool()
async def append_code(page_id: str, code: str, language: str = "plain text") -> str:
    """追加代码块。language 例如 python/javascript/typescript/shell/json/markdown"""
    block = {"object": "block", "type": "code",
             "code": {"rich_text": _rt(code), "language": language}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "已追加代码块"


@mcp.tool()
async def append_divider(page_id: str) -> str:
    """追加分割线"""
    block = {"object": "block", "type": "divider", "divider": {}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "已追加分割线"


@mcp.tool()
async def append_image(page_id: str, image_url: str) -> str:
    """通过外部 URL 追加图片"""
    block = {"object": "block", "type": "image",
             "image": {"type": "external", "external": {"url": image_url}}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "已追加图片"


@mcp.tool()
async def append_bookmark(page_id: str, url: str) -> str:
    """追加书签卡片"""
    block = {"object": "block", "type": "bookmark", "bookmark": {"url": url}}
    notion.blocks.children.append(block_id=page_id, children=[block])
    return "已追加书签"


# ---------- 评论 ----------

@mcp.tool()
async def list_comments(block_id: str) -> str:
    """列出页面或块上的评论"""
    res = notion.comments.list(block_id=block_id)
    items = res.get("results", [])
    if not items:
        return "（暂无评论）"
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
    """发表评论。提供 page_id 在页面顶部新建评论；或提供 discussion_id 回复已有讨论串"""
    if discussion_id:
        res = notion.comments.create(discussion_id=discussion_id, rich_text=_rt(text))
    elif page_id:
        res = notion.comments.create(parent={"page_id": page_id}, rich_text=_rt(text))
    else:
        return "需要提供 page_id 或 discussion_id"
    return f"已发表评论 id={res['id']}"


# ---------- 页面/块 编辑与删除 ----------

@mcp.tool()
async def update_page(page_id: str, title: str = "", icon_emoji: str = "",
                      cover_url: str = "", archived: bool = False) -> str:
    """更新页面的标题/图标/封面/归档状态（参数为空则不改动该字段）"""
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
        return "没有要更新的字段"
    notion.pages.update(page_id=page_id, **payload)
    return f"已更新页面 {page_id}"


@mcp.tool()
async def update_block_text(block_id: str, text: str) -> str:
    """更新一个带文字的块的文字内容（paragraph/heading/bulleted/numbered/to_do/quote/callout/code）"""
    block = notion.blocks.retrieve(block_id=block_id)
    btype = block.get("type", "")
    supported = {"paragraph", "heading_1", "heading_2", "heading_3",
                 "bulleted_list_item", "numbered_list_item", "to_do",
                 "quote", "callout", "code"}
    if btype not in supported:
        return f"块类型 {btype} 不支持文字更新"
    body = dict(block.get(btype, {}))
    body["rich_text"] = _rt(text)
    notion.blocks.update(block_id=block_id, **{btype: body})
    return f"已更新块 {block_id}"


@mcp.tool()
async def delete_block(block_id: str) -> str:
    """删除（归档）一个块"""
    notion.blocks.delete(block_id=block_id)
    return f"已删除块 {block_id}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
