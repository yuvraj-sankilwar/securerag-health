"""Anthropic Claude LLM client for response generation."""

import logging

import anthropic

logger = logging.getLogger(__name__)


class AnthropicLLMClient:
    """
    Async client for Anthropic Claude API.

    Handles message generation with system prompt and context messages.
    """

    def __init__(self, api_key: str, model: str, max_tokens: int):
        """
        Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key
            model: Model identifier (e.g., "claude-sonnet-4-20250514")
            max_tokens: Maximum tokens in the response
        """
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def generate(self, messages: list[dict]) -> str:
        """
        Generate a response from Claude using the provided messages.

        The first message should have role "system" (extracted as the system parameter),
        and remaining messages are passed as the messages parameter.

        Args:
            messages: List of message dicts with "role" and "content" keys.
                      First message should be the system message.

        Returns:
            Generated text response from Claude

        Raises:
            Exception: On API errors (logged and re-raised)
        """
        try:
            # Extract system message
            system_message = ""
            user_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    user_messages.append(msg)

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_message,
                messages=user_messages,
            )

            generated_text = response.content[0].text
            logger.info(
                f"LLM generated response ({len(generated_text)} chars, "
                f"input_tokens={response.usage.input_tokens}, "
                f"output_tokens={response.usage.output_tokens})"
            )
            return generated_text

        except anthropic.AuthenticationError:
            logger.error("Anthropic API authentication failed — check ANTHROPIC_API_KEY")
            raise
        except anthropic.RateLimitError:
            logger.warning("Anthropic API rate limit exceeded")
            raise
        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            raise
