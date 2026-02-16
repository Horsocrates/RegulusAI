"""
Regulus AI - Dialogue Agent
============================

Multi-turn conversation wrapper around the Anthropic Messages API.
Maintains a growing messages[] array with proper thinking block handling
for extended thinking models (Opus 4.6, Sonnet 4.5).

Each send() call:
1. Appends a user message to the conversation
2. Calls the API with the full messages array
3. Stores the complete response (including thinking blocks) for API continuity
4. Returns only the text blocks to the caller
"""

import asyncio
import os
from dataclasses import dataclass, field
from typing import Optional

MAX_RETRIES = 5
BASE_DELAY = 3.0


@dataclass
class AgentConfig:
    """Configuration for a dialogue agent."""
    name: str = ""
    model: str = "claude-opus-4-6"
    system_prompt: str = ""
    max_output_tokens: int = 64000
    thinking_budget: int = 10000
    interleaved_thinking: bool = True
    temperature: float = 1.0


class Agent:
    """Multi-turn conversation agent using the Anthropic Messages API.

    Maintains a growing messages[] array. Thinking blocks are preserved
    in the conversation for proper API multi-turn, but only text blocks
    are returned to the caller.
    """

    def __init__(self, config: AgentConfig, api_key: Optional[str] = None):
        from anthropic import AsyncAnthropic

        self.config = config
        self._client = AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        self._messages: list[dict] = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    async def send(self, content: str) -> str:
        """Send a message and return the text response.

        Appends the user message, calls the API with the full conversation,
        stores the assistant response (including thinking blocks), and
        returns only the text portions.
        """
        from anthropic import RateLimitError

        self._messages.append({"role": "user", "content": content})

        for attempt in range(MAX_RETRIES):
            try:
                kwargs: dict = {
                    "model": self.config.model,
                    "max_tokens": self.config.max_output_tokens,
                    "messages": self._messages,
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": self.config.thinking_budget,
                    },
                }
                if self.config.system_prompt:
                    kwargs["system"] = self.config.system_prompt
                if self.config.interleaved_thinking:
                    kwargs["betas"] = ["interleaved-thinking-2025-05-14"]
                if self.config.temperature != 1.0:
                    kwargs["temperature"] = self.config.temperature

                response = await self._client.messages.create(**kwargs)

                # Extract text blocks for caller, store full content for API
                text_parts = []
                for block in response.content:
                    if block.type == "text":
                        text_parts.append(block.text)

                # Store full response content (with thinking blocks) for
                # proper multi-turn conversation with the API
                self._messages.append({
                    "role": "assistant",
                    "content": response.content,
                })

                self._total_input_tokens += response.usage.input_tokens
                self._total_output_tokens += response.usage.output_tokens

                return "\n".join(text_parts)

            except RateLimitError:
                if attempt == MAX_RETRIES - 1:
                    # Remove the user message we appended — the call failed
                    self._messages.pop()
                    raise
                delay = BASE_DELAY * (2 ** attempt)
                print(
                    f"[{self.config.name}] Rate limit, retry "
                    f"{attempt + 1}/{MAX_RETRIES} in {delay:.0f}s"
                )
                await asyncio.sleep(delay)
            except Exception:
                # Remove the user message on any unrecoverable error
                self._messages.pop()
                raise

        # Should never reach here
        self._messages.pop()
        raise RuntimeError("Unreachable: all retries exhausted")

    @property
    def total_input_tokens(self) -> int:
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self._total_output_tokens

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def get_messages_snapshot(self) -> list[dict]:
        """Return a shallow copy of the messages array (for debugging)."""
        return list(self._messages)
