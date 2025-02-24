"""
title: history agent pipeline
author: 서준호
date: 2025-01-14
version: 1.0
license: MIT
description: history agent pipeline
"""

from typing import List, Union, Generator, Iterator, Dict, Any, AsyncGenerator, Tuple
import json
import uuid
from pydantic import BaseModel, Field
import requests


class PipelineConfig(BaseModel):
    configurable: Dict[str, Any] = Field(default_factory=dict)


class Pipeline:
    ENDPOINT = "http://ai_assistant:8000/cs-history/stream"

    class Valves(BaseModel):
        pass

    def __init__(self):
        self.name = "History Agent v2"
        self.valves = self.Valves()
        self.thread_id = str(uuid.uuid4())
        self.returned_ids = set()

    async def on_startup(self):
        pass

    async def on_shutdown(self):
        pass

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        # 메시지가 하나면 새로운 대화 시작
        if len(messages) == 1:
            self.thread_id = str(uuid.uuid4())

        request_body = {
            "config": {"configurable": {"thread_id": self.thread_id}},
            "messages": [{"role": "user", "content": user_message}],
        }

        try:
            response = requests.post(
                self.ENDPOINT,
                json=request_body,
                stream=True,
            )
            response.raise_for_status()
            for chunk in response.iter_lines():
                if chunk:
                    yield chunk
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield {"error": str(e)}
