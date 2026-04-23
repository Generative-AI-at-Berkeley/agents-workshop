from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
	tool_name: str
	success: bool
	data: Any = None
	error: str | None = None


class BaseTool(ABC):
	name: str
	description: str

	@abstractmethod
	async def run(self, **kwargs: Any) -> ToolResult: ...

	def to_langchain_tool(self) -> dict:
		return {
			"type": "function",
			"function": {"name": self.name, "description": self.description, "parameters": self._parameters()},
		}

	@abstractmethod
	def _parameters(self) -> dict: ...
