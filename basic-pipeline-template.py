"""
title: Basic Pipeline Template
author: your name
date: 2024-03-21
version: 1.0
license: MIT
description: Basic pipeline template for OpenWebUI
requirements: pydantic
"""

from typing import List, Union, Generator, Iterator
import os
from pydantic import BaseModel


class Pipeline:
    class Valves(BaseModel):
        KEY: str

    def __init__(self):
        self.name = "Basic Pipeline"

        # 기본 설정값 초기화
        self.valves = self.Valves(**{"KEY": "VALUE"})

    async def on_startup(self):
        # 서버 시작시 초기화 작업
        print(f"Starting pipeline: {self.name}")
        pass

    async def on_shutdown(self):
        # 서버 종료시 정리 작업
        print(f"Shutting down pipeline: {self.name}")
        pass

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        # 실제 파이프라인 로직 구현
        try:
            # 여기에 실제 처리 로직 구현
            response = f"Received message: {user_message}"
            return response

        except Exception as e:
            return f"Error in pipeline: {str(e)}"
