"""OpenAI GPT LLM client for response generation."""

import logging

from openai import AsyncOpenAI, AuthenticationError, RateLimitError

logger = logging.getLogger(__name__)


class OpenAILLMClient:
    """
    Async client for OpenAI Chat Completions API.

    Handles message generation with system prompt and context messages.
    """

    def __init__(self, api_key: str, model: str, max_tokens: int):
        """
        Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model identifier (e.g., "gpt-4o")
            max_tokens: Maximum tokens in the response
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def generate(self, messages: list[dict]) -> str:
        """
        Generate a response from OpenAI using the provided messages.

        Messages are passed directly — the OpenAI Chat Completions API
        natively supports the system/user/assistant role format.

        Args:
            messages: List of message dicts with "role" and "content" keys.
                      First message should be the system message.

        Returns:
            Generated text response from OpenAI

        Raises:
            Exception: On API errors (logged and re-raised)
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=messages,
            )

            generated_text = response.choices[0].message.content
            logger.info(
                f"LLM generated response ({len(generated_text)} chars, "
                f"prompt_tokens={response.usage.prompt_tokens}, "
                f"completion_tokens={response.usage.completion_tokens})"
            )
            return generated_text

        except AuthenticationError:
            logger.error("OpenAI API authentication failed — check OPENAI_API_KEY")
            raise
        except RateLimitError:
            logger.warning("OpenAI API rate limit exceeded")
            raise
        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            raise
