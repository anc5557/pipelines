"""
title: history agent pipeline
author: 서준호
date: 2025-01-14
version: 1.0
license: MIT
description: history agent pipeline
"""

from typing import List, Union, Generator, Iterator, Dict, Any, AsyncGenerator
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

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:

        if len(messages) == 1:
            self.thread_id = str(uuid.uuid4())

        request_body = {
            "config": {"configurable": {"thread_id": self.thread_id}},
            "messages": {"role": "user", "content": user_message},
        }
        responses = []

        try:
            response = requests.post(
                self.ENDPOINT,
                json=request_body,
                stream=True,
            )
            response.raise_for_status()
        except Exception as e:
            responses.append({"error": str(e)})
            return responses

        # 수정됨: streaming 응답에서 메시지 카테고리(역할 또는 tool 이름)와 메시지를 파싱하여 반환하는 제너레이터 함수 구현
        def parse_stream():
            import ast  # 문자열을 dict로 변환하기 위해 사용

            for line in response.iter_lines():
                if line:
                    line_decoded = (
                        line.decode("utf-8") if isinstance(line, bytes) else line
                    )
                    if line_decoded.startswith("data: "):
                        data_line = line_decoded[len("data: ") :].strip()
                        if data_line == "[DONE]":
                            break
                        try:
                            data_dict = ast.literal_eval(data_line)
                        except Exception as ex:
                            continue
                        if "agent" in data_dict:
                            msg_list = data_dict["agent"].get("messages", [])
                            if msg_list:
                                msg_obj = msg_list[0]
                                # agent 응답인 경우, response_metadata의 message에서 role을 추출
                                role = "assistant"
                                if (
                                    "response_metadata" in msg_obj
                                    and "message" in msg_obj["response_metadata"]
                                ):
                                    role = msg_obj["response_metadata"]["message"].get(
                                        "role", "assistant"
                                    )
                                message_text = msg_obj.get("content", "")
                                yield {"category": role, "message": message_text}
                        elif "tools" in data_dict:
                            msg_list = data_dict["tools"].get("messages", [])
                            if msg_list:
                                msg_obj = msg_list[0]
                                tool_name = msg_obj.get("name", "tool")
                                message_text = msg_obj.get("content", "")
                                yield {"category": tool_name, "message": message_text}

        return parse_stream()  # 수정됨: 제너레이터 반환
