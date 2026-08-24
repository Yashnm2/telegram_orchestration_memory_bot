# Run Guide

This guide explains how to set up, test, and run the Telegram orchestration bot on **Windows** or **macOS**.

## Before you begin

You need:

- Python **3.10 or newer**. The bot uses Python syntax that is not supported by
  older releases.
- An internet connection while installing packages and running the bot.
- A Telegram bot token from [BotFather](https://t.me/BotFather).
- An AI Lodge API key, or another OpenAI-compatible key supported by the
  project.

## Command differences at a glance

| Task | Windows PowerShell | macOS Terminal |
|---|---|---|
| Python command | `py -3` | `python3` |
| Activate environment | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| Copy a file | `Copy-Item` | `cp` |
| Stop the bot | `Ctrl+C` | `Control+C` |

## First-time setup

### 1. Open the project folder

**Windows PowerShell**

```powershell
cd "C:\path\to\telegram_orchestration_memory_bot"
```

**macOS Terminal**

Replace `/path/to` with the location where you saved the project:

```bash
cd "/path/to/telegram_orchestration_memory_bot"
```

### 2. Check that Python is installed

| Windows PowerShell | macOS Terminal |
|---|---|
| `py -3 --version` | `python3 --version` |

Confirm that the reported version is 3.10 or newer. If the command fails or
reports an older version, install a current Python release from
[python.org](https://www.python.org/downloads/). On Windows, enable the Python
launcher when the installer offers that option.

### 3. Create a virtual environment

| Windows PowerShell | macOS Terminal |
|---|---|
| `py -3 -m venv .venv` | `python3 -m venv .venv` |

The virtual environment keeps this project's packages separate from other Python projects.

### 4. Activate the virtual environment

| Windows PowerShell | macOS Terminal |
|---|---|
| `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |

If Windows PowerShell blocks activation, run this command in the same window and then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

This PowerShell step is **not needed on macOS**.

### 5. Install the required packages

After activation, `python` refers to the interpreter inside `.venv` on both
operating systems:

```text
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 6. Create the `.env` file

| Windows PowerShell | macOS Terminal |
|---|---|
| `Copy-Item .env.example .env` | `cp .env.example .env` |

Open `.env` in a text editor and replace the example values with your real keys:

```dotenv
AI_LODGE_API_KEY=your_real_ai_key
TELEGRAM_BOT_TOKEN=your_real_telegram_bot_token
```

Leave `AI_LODGE_BASE_URL` and `AI_LODGE_MODEL` at their example defaults unless
your API provider gave you different values. The code also accepts
`OPENAI_API_KEY` or `APIYI_API_KEY` in place of `AI_LODGE_API_KEY`.

> [!IMPORTANT]
> Do not share `.env` or commit it to a public repository.

## Test the project

Run the offline tests before starting the bot:

```text
python -m unittest -v
```

The final output should say `OK`. These tests do not send real Telegram messages or make paid AI requests.

## Start the bot

```text
python bot.py
```

The terminal should display:

```text
Bot started - press Ctrl+C to stop
```

Keep the PowerShell or Terminal window open while using the bot.

## Test it in Telegram

These steps are the same on Windows and macOS.

First, send:

```text
/start
```

Then test its memory by sending these messages one at a time:

```text
My project is called Moss.
What is my project called?
/reset
What is my project called?
```

Before `/reset`, the bot should remember **Moss**. After `/reset`, it should no longer have that conversation in memory.

To test the Python-code route, send:

```text
how many r's are in strawberry
```

The reply should begin with `Routed to: Python code` and answer **3**.

## Stop the bot

Return to PowerShell or Terminal and press `Ctrl+C` (`Control+C` on a Mac keyboard).

## Run it again later

After the first-time setup, only three commands are needed.

**Windows PowerShell**

```powershell
cd "C:\path\to\telegram_orchestration_memory_bot"
.\.venv\Scripts\Activate.ps1
python bot.py
```

**macOS Terminal**

```bash
cd "/path/to/telegram_orchestration_memory_bot"
source .venv/bin/activate
python bot.py
```

When finished, either close the terminal or leave the virtual environment with:

```text
deactivate
```

## Common problems

### `TELEGRAM_BOT_TOKEN is missing from .env`

Check that `.env` exists in the project folder and contains the correct Telegram token.

### `No API key found`

Check that `.env` contains a valid `AI_LODGE_API_KEY`, `OPENAI_API_KEY`, or
`APIYI_API_KEY` value.

### The bot does not answer

- Confirm that `bot.py` is still running.
- Check PowerShell or Terminal for an error.
- Confirm that the token belongs to the Telegram bot you are messaging.

### The bot forgot the conversation

Memory exists only while `bot.py` is running. Restarting the program clears all memory. The bot keeps only the latest three exchanges in each chat.

### `ModuleNotFoundError`

Activate `.venv`, then install the dependencies again:

```text
python -m pip install -r requirements.txt
```

### macOS says `python3: command not found`

Install a current Python release from [python.org](https://www.python.org/downloads/),
close and reopen Terminal, and repeat the version check.

### Telegram reports `Unauthorized`

The value of `TELEGRAM_BOT_TOKEN` is invalid. Copy the current token from
BotFather into `.env`, without quotes or extra spaces, and restart the bot.
