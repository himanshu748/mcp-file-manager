# 🤖 MCP File Manager Server

> A zero-dependency Python MCP server that gives Claude the ability to manage files through plain English.

Built as part of the **[Codédex Monthly Challenge](https://www.codedex.io/)** — *"Build Your Own MCP Server with Python"*.

## What it does

Connect this server to Claude Desktop and talk to your files naturally:

> *"Read my notes.txt"* → Claude calls `read_file` and shows you the contents.  
> *"Add dark chocolate to my shopping list"* → Claude calls `append_to_file`.  
> *"Search all my files for 'budget'"* → Claude calls `search_files` across every file.

## Tools

| Tool | Description |
|---|---|
| `list_files` | List all files in the workspace with sizes and timestamps |
| `read_file` | Read the contents of a file |
| `write_file` | Create or overwrite a file |
| `append_to_file` | Append text to an existing file |
| `delete_file` | Delete a file |
| `search_files` | Search for a string across all files |

## Quick Start

**No pip install needed** — standard library only.

```bash
git clone https://github.com/your-username/mcp-file-manager
cd mcp-file-manager
python3 test_server.py   # verify it works
```

## Connect to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "file-manager": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp-file-manager/server.py"]
    }
  }
}
```

Restart Claude Desktop. Look for the 🔨 hammer icon — you're live!

## Project Structure

```
mcp-file-manager/
├── server.py          ← The MCP server
├── test_server.py     ← Test harness (no Claude needed)
└── workspace/         ← Sandboxed file storage (auto-created)
```

## Tutorial

Read the full step-by-step tutorial on [Codédex](https://www.codedex.io/) ← *update link after publish*

## License

MIT
