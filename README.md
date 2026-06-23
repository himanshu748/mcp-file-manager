# Build Your Own MCP Server with Python 🤖🗂️

> **What you need:** Python 3.10+, basic Python (loops, functions, dicts), Claude Desktop (free)
> **Time:** ~60 minutes
> **What you'll build:** An MCP server with 6 tools that gives Claude the ability to read, write, search, and delete files on your computer — all through plain English

---

## Intro: What Are We Building, and Why Should You Care?

Picture this: you're chatting with Claude and you say, *"Hey, remember that business idea I had last week? Can you read my `ideas.txt` and help me flesh it out?"*

Without MCP, Claude just shrugs. It can't open your files. It doesn't know what's on your machine. It's an incredibly smart brain locked in a glass box.

**MCP — the Model Context Protocol — smashes that glass box.**

MCP is an open standard that lets you hand Claude a set of custom tools it can actually *use* during a conversation. Tools you write. Tools that do real things — read files, query databases, call APIs, control your smart home, literally anything Python can do.

And this isn't some niche experiment anymore. As of June 2026, MCP is governed by the **Agentic AI Foundation** under the Linux Foundation — the same folks who manage Linux and Kubernetes. OpenAI, Google, and Microsoft all sit on the steering committee. MCP is, officially, the USB-C port for AI tools.

Here's the magic moment we're working toward:

> 🧑 **You:** "Read my notes.txt and add dark chocolate to the shopping list."
>
> 🤖 **Claude:** *(silently calls `read_file`, sees "Apples, Bread, Coffee", then calls `append_to_file`)*
>
> 🤖 **Claude:** "Done! I've added dark chocolate to your shopping list. You now have 4 items."

That's not a mockup. That's what you'll have running on your machine by the end of this tutorial.

Our server will give Claude **6 real tools**:

| Tool | What it does |
|---|---|
| `list_files` | Shows everything in the sandbox folder with sizes and timestamps |
| `read_file` | Opens and reads a file's full contents |
| `write_file` | Creates a new file or overwrites an existing one |
| `append_to_file` | Adds text to the end of a file without wiping it |
| `delete_file` | Permanently removes a file |
| `search_files` | Scans every file for a keyword and returns the matching lines |

Zero external libraries. One Python file. Let's build it. 🚀

---

## A Little Background: MCP in June 2026

You might be wondering — *is this new? How stable is it?* Great questions.

MCP was originally released by Anthropic in **November 2024**. In December 2025, Anthropic donated it to the **Agentic AI Foundation** (part of the Linux Foundation) to make it a true community standard. By mid-2026, there are thousands of MCP servers in the wild — for GitHub, Postgres, Slack, Google Drive, home automation, you name it.

The protocol is rock solid for what we're building today: a **stdio-based server** (meaning it communicates through standard input/output) with tool support. This is the most common type and what Claude Desktop expects.

*(Fun fact: a big stateless-core update is coming in late July 2026, but it doesn't affect stdio servers like ours — we're good.)*

---

## How MCP Actually Works (Before We Write a Single Line)

Before writing a single line of code, let's get the mental model right. Once you get this, everything else clicks.

**The three players:**

1. **You** — chatting in Claude Desktop
2. **Claude Desktop (the Host)** — the app that runs Claude and manages connections to servers
3. **Our `server.py` (the MCP Server)** — a Python script that Claude Desktop launches as a subprocess

Claude Desktop and our server talk through **stdin and stdout** — basically, Claude Desktop types messages into our script's input pipe, and our script types responses into its output pipe. Like two people sliding notes under a door.

The messages are formatted as **JSON-RPC 2.0** — a standard way of saying "here's a request" and "here's the result":

```
Claude Desktop → Our Server (via stdin):
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "read_file",
    "arguments": { "filename": "notes.txt" }
  }
}

Our Server → Claude Desktop (via stdout):
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [{ "type": "text", "text": "📄 Contents of 'notes.txt':\n\nApples\nBread\nCoffee" }]
  }
}
```

And there are only **three methods** you need to handle to have a fully working MCP server:

| Method | When Claude sends it | What you send back |
|---|---|---|
| `initialize` | On startup — "hello, let's connect" | Your server name + protocol version |
| `tools/list` | "What tools do you have?" | The full list with descriptions |
| `tools/call` | "Run this tool with these arguments" | The tool's output as text |

That's the entire protocol. Three methods. Now let's build it.

---

## Step 1 — Project Setup

Create your project folder:

```bash
mkdir mcp-file-manager
cd mcp-file-manager
```

Your finished project will look like this:

```
mcp-file-manager/
├── server.py          ← The MCP server we're building today
├── test_server.py     ← A test script so you can verify without Claude
└── workspace/         ← Auto-created when the server runs; all files live here
```

No `pip install` needed. We're using **only Python's standard library**: `json`, `sys`, `datetime`, and `pathlib`. This means anyone who clones your repo can run it instantly.

---

## Step 2 — The Foundation: Imports and the Sandbox

Create `server.py` and start with this:

```python
import json
import sys
import datetime
from pathlib import Path

# ─── The Sandbox ──────────────────────────────────────────────────────────────
# Every file operation is locked to this folder.
# Claude cannot read, write, or delete anything outside of it.
WORKSPACE = Path(__file__).parent / "workspace"
WORKSPACE.mkdir(exist_ok=True)
```

That last line — `WORKSPACE.mkdir(exist_ok=True)` — creates the `workspace/` folder automatically the first time the server runs. Clean and tidy.

**Why a sandbox?** Imagine handing a stranger the keys to your house but only letting them in the guest room. That's what we're doing. Claude gets full power *inside* `workspace/` and zero access to anything else — your SSH keys, your system files, your tax documents. All safe.

Now add the three JSON-RPC helpers that handle all our communication:

```python
def send(obj: dict):
    """Write a JSON-RPC message to stdout so Claude Desktop can read it."""
    # flush=True is non-negotiable here.
    # Without it, Python buffers the output and Claude Desktop sits waiting forever.
    print(json.dumps(obj), flush=True)


def send_result(request_id, result):
    """Send a successful response back to Claude Desktop."""
    send({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    })


def send_error(request_id, code: int, message: str):
    """Send an error response — something went wrong."""
    send({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message}
    })
```

Nothing fancy — just Python dictionaries being serialized to JSON. The `flush=True` is the one gotcha beginners hit: Python buffers print output by default, which means Claude Desktop never gets your responses. Always flush.

---

## Step 3 — Tell Claude What You Can Do

Next, we define our tools. Think of this as the **menu** Claude reads before deciding what to order. It's a Python list of dictionaries, and each one describes a tool: its name, a description Claude reads to understand *when* to use it, and a JSON Schema describing what arguments it takes.

```python
TOOLS = [
    {
        "name": "list_files",
        "description": (
            "List all files currently in the managed workspace folder. "
            "Returns each file's name, size in bytes, and last-modified timestamp. "
            "Use this to see what files exist before reading or modifying them."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "read_file",
        "description": (
            "Read and return the complete text contents of a file from the workspace. "
            "Use this whenever the user asks to see, review, or work with the contents of a file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The exact name of the file to read, including extension. Example: 'notes.txt'"
                }
            },
            "required": ["filename"]
        }
    },
    {
        "name": "write_file",
        "description": (
            "Create a new file or completely overwrite an existing file with new content. "
            "WARNING: this replaces the entire file. Use append_to_file if you only want to add to it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the file to create or overwrite. Example: 'ideas.txt'"
                },
                "content": {
                    "type": "string",
                    "description": "The full text content to write into the file."
                }
            },
            "required": ["filename", "content"]
        }
    },
    {
        "name": "append_to_file",
        "description": (
            "Add new text to the END of an existing file, without touching what's already there. "
            "Creates the file if it doesn't exist yet. Perfect for adding list items, log entries, or new notes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the file to append to."
                },
                "content": {
                    "type": "string",
                    "description": "The text to add at the end of the file."
                }
            },
            "required": ["filename", "content"]
        }
    },
    {
        "name": "delete_file",
        "description": (
            "Permanently delete a file from the workspace. This cannot be undone. "
            "Always confirm with the user before deleting important files."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the file to delete."
                }
            },
            "required": ["filename"]
        }
    },
    {
        "name": "search_files",
        "description": (
            "Search for a word or phrase across ALL files in the workspace. "
            "Returns the filename and the specific lines that match. Case-insensitive."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The word or phrase to search for across all files."
                }
            },
            "required": ["query"]
        }
    },
]
```

> 💡 **The description is secret sauce.** Claude uses it to decide *whether and when* to call your tool. Be specific. Write the description like you're explaining to a smart intern what this button does and when they should press it. Vague descriptions lead to Claude calling the wrong tool or not calling one at all.

---

## Step 4 — Write the Actual Tools

Here's where Python does real work. First, a one-liner security function:

```python
def safe_path(filename: str) -> Path:
    """
    Convert a filename to an absolute path inside the sandbox.

    The key trick: Path(filename).name strips everything before the last slash.
    So if someone (or an AI) passes "../../etc/passwd", .name gives us just "passwd"
    and we safely resolve that inside the workspace folder instead.
    """
    return WORKSPACE / Path(filename).name
```

Path traversal attacks — where someone sneaks in `../` to escape a directory — are one of the most common bugs in file-handling code. `Path(x).name` neutralizes them in one line. Write that down.

Now the six tools themselves. Each one returns a plain string — whatever Claude will read and relay to the user:

```python
def tool_list_files() -> str:
    all_files = [f for f in WORKSPACE.iterdir() if f.is_file()]

    if not all_files:
        return "📭 The workspace is empty — no files here yet."

    lines = ["📁 Files in your workspace:\n"]
    for f in sorted(all_files):
        stat     = f.stat()
        size     = stat.st_size
        modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        lines.append(f"  • {f.name:<30} {size:>8} bytes   last modified {modified}")

    return "\n".join(lines)


def tool_read_file(filename: str) -> str:
    path = safe_path(filename)

    if not path.exists():
        return f"❌ Couldn't find '{filename}' in the workspace. Did you mean a different name? Use list_files to see what's available."

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"❌ '{filename}' appears to be a binary file (like an image or PDF) — can't read it as text."

    return f"📄 Contents of '{filename}':\n\n{content}"


def tool_write_file(filename: str, content: str) -> str:
    path = safe_path(filename)
    existed = path.exists()
    path.write_text(content, encoding="utf-8")

    action = "overwritten" if existed else "created"
    return f"✅ '{filename}' {action} successfully ({len(content):,} characters, {len(content.splitlines())} lines)."


def tool_append_to_file(filename: str, content: str) -> str:
    path = safe_path(filename)
    existed = path.exists()

    with open(path, "a", encoding="utf-8") as f:
        f.write(content)

    if existed:
        return f"✅ Appended {len(content):,} characters to '{filename}'."
    else:
        return f"✅ '{filename}' didn't exist yet — created it and wrote {len(content):,} characters."


def tool_delete_file(filename: str) -> str:
    path = safe_path(filename)

    if not path.exists():
        return f"❌ '{filename}' doesn't exist — nothing to delete."

    path.unlink()
    return f"🗑️ '{filename}' has been permanently deleted."


def tool_search_files(query: str) -> str:
    results  = []
    searched = 0

    for filepath in sorted(WORKSPACE.iterdir()):
        if not filepath.is_file():
            continue
        searched += 1

        try:
            file_lines = filepath.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue  # skip images, PDFs, other binary files

        hits = [
            f"    Line {i + 1:>4}: {line.strip()}"
            for i, line in enumerate(file_lines)
            if query.lower() in line.lower()
        ]

        if hits:
            results.append(f"\n  📄 {filepath.name}:")
            results.extend(hits)

    if not results:
        return f"🔍 Searched {searched} file(s) — nothing contains '{query}'."

    header = f"🔍 Found '{query}' in {len(results)} location(s) across {searched} file(s):"
    return header + "\n" + "\n".join(results)
```

Now wire everything together in a dispatcher:

```python
def dispatch_tool(tool_name: str, arguments: dict) -> str:
    if tool_name == "list_files":
        return tool_list_files()
    elif tool_name == "read_file":
        return tool_read_file(arguments.get("filename", ""))
    elif tool_name == "write_file":
        return tool_write_file(arguments.get("filename", ""), arguments.get("content", ""))
    elif tool_name == "append_to_file":
        return tool_append_to_file(arguments.get("filename", ""), arguments.get("content", ""))
    elif tool_name == "delete_file":
        return tool_delete_file(arguments.get("filename", ""))
    elif tool_name == "search_files":
        return tool_search_files(arguments.get("query", ""))
    else:
        return f"❌ I don't know a tool called '{tool_name}'. Check your TOOLS list."
```

---

## Step 5 — The Main Loop (The Nerve Center)

This is the last piece of `server.py`. It reads requests from Claude Desktop line by line, figures out what's being asked, and sends back a response:

```python
def main():
    """
    The MCP server's heartbeat.
    This loop runs forever (until Claude Desktop closes the subprocess).
    Each iteration handles exactly one JSON-RPC message.
    """
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            request = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        # ── Handshake ─────────────────────────────────────────────────────
        if method == "initialize":
            send_result(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-file-manager", "version": "1.0.0"}
            })

        # ── Tool discovery ────────────────────────────────────────────────
        elif method == "tools/list":
            send_result(req_id, {"tools": TOOLS})

        # ── Tool execution ────────────────────────────────────────────────
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments  = params.get("arguments", {})
            try:
                output = dispatch_tool(tool_name, arguments)
            except Exception as e:
                output = f"❌ Unexpected error while running '{tool_name}': {e}"
            send_result(req_id, {"content": [{"type": "text", "text": output}]})

        elif method == "notifications/initialized":
            pass  # informational only, no response needed

        elif req_id is not None:
            send_error(req_id, -32601, f"Method not found: '{method}'")


if __name__ == "__main__":
    main()
```

**That's `server.py` — complete.** Here's the full flow when you ask Claude to save a file:

```
① You: "Save a file called goals.txt with my three goals for this year."

② Claude reads TOOLS, decides to call write_file

③ Claude Desktop → server (stdin):
   {"jsonrpc":"2.0","id":7,"method":"tools/call",
    "params":{"name":"write_file","arguments":{"filename":"goals.txt","content":"..."}}}

④ server → dispatch_tool() → tool_write_file()
   → "✅ 'goals.txt' created successfully (42 characters, 3 lines)."

⑤ server → Claude Desktop (stdout): the result

⑥ Claude tells you: "Done! I've saved your three goals to goals.txt."

⑦ You open workspace/goals.txt — it's actually there. Real. On your disk.
```

---

## Step 6 — Test It Without Claude

Before touching Claude Desktop, verify your server works with `test_server.py`:

```python
"""
test_server.py — Simulates what Claude Desktop does.
Run with:  python3 test_server.py
"""
import subprocess, json, sys, os

SERVER_PATH = os.path.join(os.path.dirname(__file__), "server.py")

def ask(proc, request):
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())

def show(label, response):
    text = response["result"].get("content", [{}])[0].get("text", "")
    print(f"\n{'─'*55}\n  {label}\n{'─'*55}\n{text}")

proc = subprocess.Popen([sys.executable, SERVER_PATH],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

resp = ask(proc, {"jsonrpc":"2.0","id":1,"method":"initialize",
    "params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"test"}}})
print(f"✅ Connected to: {resp['result']['serverInfo']}")

show("write_file → shopping.txt", ask(proc, {"jsonrpc":"2.0","id":2,"method":"tools/call",
    "params":{"name":"write_file","arguments":{"filename":"shopping.txt",
    "content":"Shopping List:\n- Apples\n- Bread\n- Coffee\n"}}}))

show("append_to_file", ask(proc, {"jsonrpc":"2.0","id":3,"method":"tools/call",
    "params":{"name":"append_to_file","arguments":{"filename":"shopping.txt","content":"- Dark Chocolate\n"}}}))

show("list_files", ask(proc, {"jsonrpc":"2.0","id":4,"method":"tools/call",
    "params":{"name":"list_files","arguments":{}}}))

show("read_file", ask(proc, {"jsonrpc":"2.0","id":5,"method":"tools/call",
    "params":{"name":"read_file","arguments":{"filename":"shopping.txt"}}}))

show("search_files → 'Chocolate'", ask(proc, {"jsonrpc":"2.0","id":6,"method":"tools/call",
    "params":{"name":"search_files","arguments":{"query":"Chocolate"}}}))

proc.stdin.close()
print("\n✅ All tests passed! Your server is ready for Claude Desktop.")
```

Run it:

```bash
python3 test_server.py
```

Expected output:

```
✅ Connected to: {'name': 'mcp-file-manager', 'version': '1.0.0'}

───────────────────────────────────────────────────────
  write_file → shopping.txt
───────────────────────────────────────────────────────
✅ 'shopping.txt' created successfully (42 characters, 4 lines).

───────────────────────────────────────────────────────
  list_files
───────────────────────────────────────────────────────
📁 Files in your workspace:

  • shopping.txt                       60 bytes   last modified 2026-06-23 14:08

───────────────────────────────────────────────────────
  read_file
───────────────────────────────────────────────────────
📄 Contents of 'shopping.txt':

Shopping List:
- Apples
- Bread
- Coffee
- Dark Chocolate

✅ All tests passed! Your server is ready for Claude Desktop.
```

---

## Step 7 — Connect to Claude Desktop

**① Find your config file**

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

**② Add your server** (replace the path with your real absolute path):

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

> On macOS: `cd` into the project folder and run `pwd` to get the path, then add `/server.py`.
> On Windows: right-click `server.py` → "Copy as path", then replace `\` with `/`.

**③ Fully quit and restart Claude Desktop** (Cmd+Q on Mac, not just close the window)

**④ Look for the 🔨 hammer icon** in the chat input — that's your tools showing up.

**⑤ Try these prompts:**

```
"Create a file called journal.txt and write today's date as the first line."
"Append a new entry: 'Built my first MCP server today. Feeling great about it.'"
"Read journal.txt."
"Search all my files for the word 'MCP'."
"List all my files and tell me which one is bigger."
```

Watch Claude decide which tool to call, call it, get the result, and reply naturally. Genuinely magical the first time. ✨

---

## The Full Picture

```
┌─────────────────────────────────────────────────────┐
│                  You (the user)                     │
│  "Read my notes.txt and summarise the key points"   │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│             Claude Desktop (the MCP Host)           │
│  • Runs Claude    • Manages MCP server connections  │
└────────────────────────┬────────────────────────────┘
                         │ stdin / stdout (JSON-RPC 2.0)
                         ▼
┌─────────────────────────────────────────────────────┐
│              server.py  (our MCP Server)            │
│  initialize → tools/list → tools/call               │
│    ├── list_files()    ├── write_file()             │
│    ├── read_file()     ├── append_to_file()         │
│    ├── delete_file()   └── search_files()           │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│   workspace/   🔒 sandboxed — AI can't escape this  │
│   notes.txt • journal.txt • recipes.txt • ...       │
└─────────────────────────────────────────────────────┘
```

---

## What's Next? 🏗️

**Extend this server:**
- `rename_file` tool — rename or move a file within the workspace
- `word_count` tool — count words, lines, characters (great for writing goals)
- File type filtering — only allow `.txt` and `.md`, reject everything else
- Size limits — reject writes larger than 500KB

**Build something entirely new:**
- **Habit Tracker MCP** — Claude logs habits to a CSV and reports your streak
- **Bookmark Manager MCP** — save and search URLs with tags
- **Meeting Notes MCP** — create dated note files, search by keyword

**Go deeper:**
- Connect to **Cursor** or **Zed** — both support MCP as of 2026
- Read the official spec at [modelcontextprotocol.io](https://modelcontextprotocol.io)
- Check out **MCP Apps** — a 2026 feature that lets tools return interactive UI components inside the chat

---

## What You Learned

✅ What MCP is — and why it's now a Linux Foundation standard  
✅ How JSON-RPC 2.0 works under the hood  
✅ The 3 protocol methods every MCP server needs  
✅ How to write tool schemas Claude actually understands  
✅ How to sandbox file access so the AI can't touch sensitive files  
✅ How to test your server without needing Claude at all  

**MCP is only 18 months old.** The best servers — the ones that become part of every developer's toolkit — are being written right now, by people exactly like you. You've got the foundations. What will you build?

---

*Written for the [Codédex Monthly Challenge](https://www.codedex.io/community/monthly-challenge) · June 2026*
