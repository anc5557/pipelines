"""
title: history agent pipeline
author: 서준호
date: 2025-01-14
version: 1.0
license: MIT
description: history agent pipeline
"""

from typing import List, Union, Generator, Iterator
import requests
from pydantic import BaseModel


class Pipeline:
    class Valves(BaseModel):
        KEY: str

    def __init__(self):
        self.name = "History Agent"
        self.valves = self.Valves(**{"KEY": "VALUE"})

    async def on_startup(self):
        print(f"Starting pipeline: {self.name}")

    async def on_shutdown(self):
        print(f"Shutting down pipeline: {self.name}")

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:

        payload = {"question": user_message, "mode": "llm"}
        try:
            response = requests.post(
                "http://ai_assistant:8000/cs-history/query", json=payload
            )
            if response.ok:
                try:
                    data = response.json()
                    query = data.get("sql_query")
                    result = f"**쿼리**\n{query}\n\n"
                    try:
                        sync_response = requests.get(
                            "http://ai_assistant:8000/cs-history/sync/last-time"
                        )
                        if sync_response.ok:
                            sync_data = sync_response.json()
                            sync_time = sync_data.get("sync_time")
                            if sync_time:
                                sync_date_time = sync_time.replace("T", " ")
                                result += f"**히스토리시트 동기화 시간**\n{sync_date_time}\n\n"
                            else:
                                result += "**히스토리시트 동기화 시간 없음**\n\n"
                        else:
                            result += "**히스토리시트 동기화 시간 조회 실패**\n\n"

                    except Exception as e:
                        result += f"**기준 시간 조회 오류: {str(e)}**\n\n"
                    result += "**쿼리 결과**\n"

                    query_result = data.get("query_result")
                    if (
                        query_result
                        and isinstance(query_result, list)
                        and len(query_result) > 0
                    ):
                        all_keys = set()
                        for row in query_result:
                            all_keys.update(row.keys())
                        keys = list(all_keys)
                        header = "| " + " | ".join(keys) + " |"
                        separator = "| " + " | ".join(["---"] * len(keys)) + " |"
                        rows = []
                        for row in query_result:
                            row_values = [str(row.get(k, "")) for k in keys]
                            rows.append("| " + " | ".join(row_values) + " |")
                        table = header + "\n" + separator + "\n" + "\n".join(rows)
                        result += table
                    else:
                        result += "결과 없음."
                    result += "\n\n"
                    result += f"{data.get('analysis', '')}\n\n"
                    return result
                except Exception:
                    return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error in pipeline: {str(e)}"
