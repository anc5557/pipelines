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
        # 이미 반환한 메시지 id를 저장하여 중복 반환 방지
        self.returned_ids = set()

    async def on_startup(self):
        pass

    async def on_shutdown(self):
        pass

    async def stream_response(self, response: Generator) -> AsyncGenerator[str, None]:
        for chunk in response:
            if chunk:
                yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    def categorized_generators(self, responses: List[dict]) -> Tuple[
        Generator[dict, None, None],
        Generator[dict, None, None],
        Generator[dict, None, None],
    ]:
        """
        입력된 응답 리스트에서 메시지를 순회하며 세 가지 범주로 나누어 제너레이터를 반환합니다.
          1. AI 메시지 – 툴 호출: name이 "history_agent"이고 tool_calls 필드가 존재하며 비어있지 않은 경우.
          2. AI 메시지 – 순수 응답: name이 "history_agent"이고 tool_calls가 없거나 빈 경우.
          3. 툴 메시지 – 툴 응답: 메시지에 "tool_call_id" 필드가 있는 경우.

        이미 반환한 메시지(id가 self.returned_ids에 포함된)는 제외합니다.
        """
        ai_tool_calls = []
        ai_pure = []
        tool_responses = []

        for response in responses:
            for message in response.get("messages", []):
                msg_id = message.get("id")
                if not msg_id:
                    continue
                # 이미 반환한 메시지이면 건너뜀
                if msg_id in self.returned_ids:
                    continue
                self.returned_ids.add(msg_id)

                # AI 메시지: name 필드가 "history_agent"인 경우
                if message.get("name") == "history_agent":
                    if message.get("tool_calls") and len(message.get("tool_calls")) > 0:
                        ai_tool_calls.append(message)
                    else:
                        ai_pure.append(message)
                # 툴 메시지: tool_call_id 필드가 존재하는 경우
                elif "tool_call_id" in message:
                    tool_responses.append(message)

        return (
            (msg for msg in ai_tool_calls),
            (msg for msg in ai_pure),
            (msg for msg in tool_responses),
        )

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Tuple[
        Generator[dict, None, None],
        Generator[dict, None, None],
        Generator[dict, None, None],
    ]:
        """
        - 스트리밍 응답을 받아 JSON 파싱 후, 메시지를 세 가지 범주로 분류하여
          Generator 형식으로 반환합니다.
        - 메시지가 하나인 경우 새로운 대화를 위해 thread_id를 새로 생성합니다.
        - 이미 반환한 메시지(id)는 self.returned_ids에 기록하여 중복 반환을 방지합니다.
        """
        # 메시지가 하나면 새로운 대화 시작
        if len(messages) == 1:
            self.thread_id = str(uuid.uuid4())

        request_body = {
            "config": {"configurable": {"thread_id": self.thread_id}},
            "messages": ["human", user_message],
        }
        responses = []

        try:
            response = requests.post(
                self.ENDPOINT,
                json=request_body,
                stream=True,
            )
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8").strip()
                    # 종료 신호이면 중단
                    if decoded_line == "data: [DONE]":
                        break
                    # "data:" 접두어 제거
                    if decoded_line.startswith("data:"):
                        json_str = decoded_line[len("data:") :].strip()
                    else:
                        json_str = decoded_line
                    try:
                        obj = json.loads(json_str)
                        responses.append(obj)
                    except Exception as e:
                        # JSON 파싱 오류 발생 시 해당 라인은 무시합니다.
                        continue
        except Exception as e:
            responses.append({"error": str(e)})

        # 파싱된 응답 리스트를 세 가지 범주의 제너레이터로 반환
        return self.categorized_generators(responses)
