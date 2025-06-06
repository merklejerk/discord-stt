import os
import aiofiles
from openai import AsyncClient
from typing import List, Optional
from dataclasses import dataclass

import src.config as config
from .logging import LogEntry

@dataclass
class WrapupFiles:
    outline_path: Optional[str]
    chatlog_path: str

OUTPUT_DIR = "wrapups"

def _to_bullet_list(items: List[any]) -> str:
    return "\n".join(f"- {str(item).replace('\n', '')}" for item in items)

_OPENAI_CLIENT: Optional[AsyncClient] = None

def _get_openai_client() -> Optional[AsyncClient]:
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        if config.OPENAI_API_KEY:
            _OPENAI_CLIENT = AsyncClient(api_key=config.OPENAI_API_KEY)
    return _OPENAI_CLIENT

async def _write_chatlog(chatlog_rows: List[str], name: str) -> str:
    """
    Writes the chat log to a file and returns the file path.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    chatlog_path = os.path.join(OUTPUT_DIR, f"{name}_transcript.log")
    async with aiofiles.open(chatlog_path, "w", encoding="utf-8") as outfile:
        await outfile.write("\n".join(chatlog_rows))
    return chatlog_path

async def _create_summary(chatlog_rows: List[str], name: str) -> Optional[str]:
    """
    Sends the chatlog to OpenAI and writes the summary markdown file. Returns the file path.
    """
    client = _get_openai_client()
    if not client:
        return None

    system_msg = (
        "You will be given a raw voice chat transcript of a D&D 5e game session. "
        "Be aware that the transcript is generated by an AI speech-to-text model and contains many errors, misinterpretations, and artifacts. "
        "You will need to internally account for and correct mistakes in order to form a coherent understanding of the story and scenes. "
        "The model will occasionally hallucinate nonsense phrases and may interpret captured noises as \"Thank you\" or \"I don't know\". or \"Bye\" or 'I love you\", and other common phrases, so watch out for those. "
        "After interpreting the transcript, generate a detailed and coherent recap, suitable for use as a player's reference material for subsequent esssions. "
        "Within each scene recap:\n"
        "- Incorporate memorable or defining quotes that occured during that scene.\n"
        "- Any items exchanged, rewards earned, discoveries, or significant plot developments should be noted in detail.\n"
        "- Highlight any funny or unexpected moments and roleplay elements.\n"
        "- For combat, it's okay to only cover the most impactful actions, but be sure to include the outcome of the encounter.\n"
        "Make sure your recap follows the order of events as they unfold in the transcript. Do not make up quotes, and always attribute them."
        "Maintain a playful, engaging, and enthusiastic tone without being long-winded.\n"
        f"{(
            "Here are some other tips:\n"
            f"{_to_bullet_list(config.TIPS)}\n"
            if config.TIPS else ""
        )}\n"
        "\nOnly output the session recap and nothing else."
    )
    user_msg = _to_bullet_list(chatlog_rows)
    print(f"Using model: {config.OPENAI_GPT_MODEL}...")
    response = await client.chat.completions.create(
        model=config.OPENAI_GPT_MODEL,
        messages=[
            { "role": "system", "content": system_msg },
            { "role": "user", "content": user_msg },
        ],
        max_completion_tokens=10240,
        temperature=0.05,
    )
    outline = response.choices[0].message.content
    md_path = os.path.join(OUTPUT_DIR, f"{name}_outline.md")
    async with aiofiles.open(md_path, "w", encoding="utf-8") as mdfile:
        await mdfile.write(outline)
    return md_path

async def create_wrapup_from_log_entries(entries: List[LogEntry], name: str, outline: bool = True) -> WrapupFiles:
    """
    Given a list of log entries, sorts by timestamp, writes a chatlog, and (optionally) sends to OpenAI for processing.
    The 'name' parameter determines the filenames it writes to.
    If outline is False, only the chatlog is generated and no summary is created.
    Returns the paths to the generated files.
    """
    entries.sort(key=lambda x: x.timestamp)
    chatlog_rows = [
        f"{config.USERNAME_MAP.get(e.user_name, e.user_name)}: {e.content}"
        for e in entries
    ]
    chatlog_path = await _write_chatlog(chatlog_rows, name)
    md_path = None
    if outline:
        md_path = await _create_summary(chatlog_rows, name)
    return WrapupFiles(outline_path=md_path, chatlog_path=chatlog_path)
