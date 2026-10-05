import os
from typing import TypeVar

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel

load_dotenv()

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        self.model = os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-20b",
        )

        self.timeout = float(
            os.getenv("GROQ_TIMEOUT", "30")
        )

        self.max_retries = int(
            os.getenv("GROQ_MAX_RETRIES", "2")
        )

        self.client = Groq(
            api_key=api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    def generate_structured(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            response_model: type[T],
    ) -> T:
        response = self.client.chat.completions.create(
            model = self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema":response_model.model_json_schema(),
                    "strict": True,
                },
            },
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError("LLM returned an empty response")

        return response_model.model_validate_json(content)