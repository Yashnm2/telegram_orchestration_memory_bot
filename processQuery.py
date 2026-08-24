"""Orchestrate direct answers, generated Python, and website reading."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from enum import Enum
from typing import Any

import requests
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

API_BASE_URL = os.getenv("AI_LODGE_BASE_URL", "https://api.apiyi.com/v1")
MODEL = os.getenv("AI_LODGE_MODEL", "gpt-4nano")


class Route(str, Enum):
    """Routes supported by the orchestration pipeline."""

    DIRECT = "DIRECT"
    CODE = "CODE_REQUIRED"
    WEB = "WEBSCRAPE"


ORCHESTRATOR_PROMPT = """
You are an intelligent task router.
Given a user query, you must decide if you can answer it directly, if it
requires writing a Python script, or if it requires reading a website.

RULES:
1. GENERAL BIAS: Whenever a query involves counting, math, logic, precise
   string/text manipulation, data processing, or anything where a
   deterministic programmatic answer is more reliable than an LLM guess, you
   MUST route to code.
2. If you can answer directly (pure general knowledge, simple facts,
   subjective text generation), reply starting EXACTLY with "DIRECT: "
   followed by your answer.
3. If you route to code, reply starting EXACTLY with "CODE_REQUIRED: "
   followed by a detailed instruction for a programmer to write the script.
4. WEBSCRAPING: If the user asks you to read, summarize, or extract information
   from a specific website or URL, reply starting EXACTLY with "WEBSCRAPE: "
   followed ONLY by the raw URL.

WARNING: You are an LLM and prone to hallucinations with numbers, counting,
formatting, and strict logic. When in doubt, prefer CODE_REQUIRED!
""".strip()

CODER_PROMPT = """
You are a Python expert. Your job is to write a standalone Python script to
solve the user's task.
- Output ONLY valid, executable Python code.
- Do NOT include markdown wrappers like ```python.
- Print the final result to stdout using `print()` so it can be captured.
""".strip()

SYNTHESIZER_PROMPT = """
You are an AI assistant. You will be provided with the user's original query
and the raw console output from a Python script or web scraper that was
executed to solve it. Your job is to formulate a friendly, human-readable
final response based on the output.
""".strip()

AuditEntry = dict[str, Any]


def make_client() -> OpenAI:
    """Create the OpenAI-compatible AI Lodge client."""
    api_key = (
        os.getenv("AI_LODGE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("APIYI_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "No API key found. Add AI_LODGE_API_KEY, OPENAI_API_KEY, or APIYI_API_KEY to .env"
        )
    return OpenAI(api_key=api_key, base_url=API_BASE_URL)


def _chat(client: OpenAI, system_prompt: str, user_text: str,) -> tuple[str, dict[str, Any] | None]:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )
    text = response.choices[0].message.content.strip()
    usage = response.usage.model_dump() if response.usage else None
    return text, usage


def _clean_generated_code(script_code: str) -> str:
    cleaned = script_code.strip()
    cleaned = re.sub(r"^```python\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned


def run_python_script(script_code: str) -> str:
    """Execute generated Python and capture stdout or stderr."""
    temp_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(_clean_generated_code(script_code))
            temp_path = temp_file.name

        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            return f"[SUCCESS] Output:\n{result.stdout}"
        return f"[ERROR] Error:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "[ERROR] Execution timed out."
    except Exception as error:
        return f"[ERROR] Exception occurred: {error}"
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def scrape_website(url: str) -> str:
    """Read a public website through Jina.ai's reader API."""
    clean_url = url.strip().strip("'\"<>")
    reader_url = (
        clean_url
        if clean_url.startswith("https://r.jina.ai/")
        else f"https://r.jina.ai/{clean_url}"
    )

    try:
        response = requests.get(reader_url, timeout=15)
        if response.status_code == 200:
            return f"[SUCCESS] Web Content:\n{response.text}"
        return (
            f"[ERROR] Failed to fetch: Status {response.status_code}\n"
            f"Response: {response.text}"
        )
    except Exception as error:
        return f"[ERROR] Exception occurred while scraping: {error}"


def _audit_entry(
    agent: str,
    input_text: str,
    output_text: str,
    *,
    detail: str,
    route: Route | None = None,
    usage: dict[str, Any] | None = None,
) -> AuditEntry:
    entry: AuditEntry = {
        "agent": agent,
        "stage": agent,
        "input": input_text,
        "output": output_text,
        "detail": detail,
    }
    if route is not None:
        entry["route"] = route.value
    if usage is not None:
        entry["usage"] = usage
    return entry


def _route_from_response(response: str) -> Route | None:
    for route in Route:
        if response.startswith(f"{route.value}:"):
            return route
    return None


def process_query(user_query: str) -> tuple[str, list[AuditEntry]]:
    """Run the notebook's orchestration pipeline for one user query."""
    client = make_client()
    audit_log: list[AuditEntry] = []

    orchestrator_result, usage = _chat(client, ORCHESTRATOR_PROMPT, user_query)
    route = _route_from_response(orchestrator_result)
    audit_log.append(
        _audit_entry(
            "Orchestrator",
            user_query,
            orchestrator_result,
            route=route,
            detail="route selected" if route else "invalid route",
            usage=usage,
        )
    )

    if route is Route.DIRECT:
        answer = orchestrator_result.removeprefix("DIRECT:").strip()
        return answer, audit_log

    if route is Route.CODE:
        coding_task = orchestrator_result.removeprefix("CODE_REQUIRED:").strip()
        generated_code, usage = _chat(client, CODER_PROMPT, coding_task)
        audit_log.append(
            _audit_entry(
                "Coder",
                coding_task,
                generated_code,
                detail="Python generated",
                usage=usage,
            )
        )

        execution_output = run_python_script(generated_code)
        execution_detail = (
            "completed" if execution_output.startswith("[SUCCESS]") else "failed"
        )
        audit_log.append(
            _audit_entry(
                "Execution",
                generated_code,
                execution_output,
                detail=execution_detail,
            )
        )
        synthesizer_input = (
            f"Original Query: {user_query}\n\nScript Output: {execution_output}"
        )

    elif route is Route.WEB:
        target_url = orchestrator_result.removeprefix("WEBSCRAPE:").strip()
        scrape_output = scrape_website(target_url)
        logged_output = (
            f"{scrape_output[:1000]}... [TRUNCATED FOR LOG]"
            if len(scrape_output) > 1000
            else scrape_output
        )
        audit_log.append(
            _audit_entry(
                "Webscraper (Jina.ai)",
                target_url,
                logged_output,
                detail="page retrieved",
            )
        )
        synthesizer_input = (
            f"Original Query: {user_query}\n\nWebsite Content: {scrape_output}"
        )

    else:
        error = (
            "[Error] Orchestrator failed to follow routing protocol. "
            f"Raw output: {orchestrator_result}"
        )
        audit_log.append(
            _audit_entry(
                "Error",
                orchestrator_result,
                error,
                detail="unsupported router response",
            )
        )
        return error, audit_log

    final_result, usage = _chat(client, SYNTHESIZER_PROMPT, synthesizer_input)
    audit_log.append(
        _audit_entry(
            "Synthesizer",
            synthesizer_input,
            final_result,
            detail="response created",
            usage=usage,
        )
    )
    return final_result, audit_log


# Backwards-compatible alias used in the workshop material.
processQuery = process_query


if __name__ == "__main__":
    prompt = input("Enter a test question: ").strip()
    if not prompt:
        raise SystemExit("Please enter a question.")

    result, audit = process_query(prompt)
    print(f"\nAnswer:\n{result}")
    print(f"\nRoute: {audit[0].get('route', 'ERROR')}")
