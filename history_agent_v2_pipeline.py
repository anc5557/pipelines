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
import logging  # 로깅 추가
import json

# 로거 설정
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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
        print(f"[Init] Pipeline initialized with thread_id: {self.thread_id}")

    async def on_startup(self):
        pass

    async def on_shutdown(self):
        pass

    async def stream_response(self, response: Generator) -> AsyncGenerator[str, None]:
        for chunk in response:
            if chunk:
                if not isinstance(chunk, str):
                    chunk = json.dumps(chunk)
                yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:

        if len(messages) == 1:
            self.thread_id = str(uuid.uuid4())
            print(f"[New Conversation] Started with thread_id: {self.thread_id}")

        request_body = {
            "config": {"configurable": {"thread_id": self.thread_id}},
            "messages": [{"role": "user", "content": user_message}],
        }
        print(f"[Request] Body: {request_body}")
        responses = []

        try:
            print(f"[Request] Sending to {self.ENDPOINT}")
            response = requests.post(
                self.ENDPOINT,
                json=request_body,
                stream=True,
            )
            response.raise_for_status()
        except Exception as e:
            print(f"[Error] Request failed: {str(e)}")
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
                    print(f"[Stream] Received: {line_decoded}")
                    if line_decoded.startswith("data: "):
                        data_line = line_decoded[len("data: ") :].strip()
                        if data_line == "[DONE]":
                            print("[Stream] Completed")
                            break
                        try:
                            data_dict = ast.literal_eval(data_line)
                            print(f"[Parse] Data: {data_dict}")
                        except Exception as ex:
                            print(f"[Warning] literal_eval failed: {ex}")
                            import re

                            m = re.search(r"content\s*=\s*'([^']*)'", data_line)
                            if m:
                                message_text = m.group(1)
                                if "agent" in data_line:
                                    yield json.dumps(
                                        {
                                            "category": "assistant",
                                            "message": message_text,
                                        }
                                    )
                                elif "tools" in data_line:
                                    yield json.dumps(
                                        {"category": "tool", "message": message_text}
                                    )
                            continue
                        if "agent" in data_dict:
                            print("[Process] Agent message")
                            msg_list = data_dict["agent"].get("messages", [])
                            if msg_list:
                                msg_obj = msg_list[0]
                                role = "assistant"
                                if (
                                    "response_metadata" in msg_obj
                                    and "message" in msg_obj["response_metadata"]
                                ):
                                    role = msg_obj["response_metadata"]["message"].get(
                                        "role", "assistant"
                                    )
                                message_text = msg_obj.get("content", "")
                                yield json.dumps(
                                    {"category": role, "message": message_text}
                                )
                        elif "tools" in data_dict:
                            print("[Process] Tool message")
                            msg_list = data_dict["tools"].get("messages", [])
                            if msg_list:
                                msg_obj = msg_list[0]
                                tool_name = msg_obj.get("name", "tool")
                                message_text = msg_obj.get("content", "")
                                yield json.dumps(
                                    {"category": tool_name, "message": message_text}
                                )

        return self.stream_response(parse_stream())
