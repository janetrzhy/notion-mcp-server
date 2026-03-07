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
    """读取Notion页面的全部内容"""
    blocks = notion.blocks.children.list(block_id=page_id, page_size=100)
    texts = []
    for block in blocks.get("results", []):
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})
        if "rich_text" in block_data:
            text = "".join([t.get("plain_text", "") for t in block_data["rich_text"]])
            if block_type.startswith("heading"):
                text = f"\n{'#' * int(block_type[-1])} {text}"
            texts.append(text)
        elif block_type == "child_page":
            texts.append(f"\n[子页面: {block_data.get('title', 'Untitled')}] id={block['id']}")
        elif block_type == "child_database":
            texts.append(f"\n[子数据库: {block_data.get('title', 'Untitled')}] id={block['id']}")
    return "\n".join(texts) if texts else "（页面为空或内容无法读取）"

@mcp.tool()
async def append_to_page(page_id: str, text: str) -> str:
    """在Notion页面末尾追加一段文字"""
    notion.blocks.children.append(
        block_id=page_id,
        children=[{
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": text}}]
            }
        }]
    )
    return f"已追加内容到页面 {page_id}"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")