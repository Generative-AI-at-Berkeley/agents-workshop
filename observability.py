from __future__ import annotations

import contextlib
from typing import Any

import structlog

from config.settings import get_settings

log = structlog.get_logger(__name__)

_client: Any | None = None
_initialized = False


def get_langfuse_client() -> Any | None:
	global _client, _initialized
	if _initialized:
		return _client
	_initialized = True
	settings = get_settings()
	if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
		return None
	try:
		from langfuse import Langfuse

		_client = Langfuse(
			public_key=settings.LANGFUSE_PUBLIC_KEY,
			secret_key=settings.LANGFUSE_SECRET_KEY,
			host=settings.LANGFUSE_HOST,
		)
	except Exception:
		log.exception("langfuse_init_failed")
		_client = None
	return _client


def reset_langfuse_client() -> None:
	global _client, _initialized
	_client = None
	_initialized = False


class _NoopObservation:
	def update(self, **_kwargs: Any) -> None:
		return None

	def end(self, **_kwargs: Any) -> None:
		return None


class _TraceContext:
	"""Context manager that wraps a Langfuse root span with session propagation.

	Uses a class instead of @contextlib.contextmanager to avoid RuntimeError when
	_AgnosticContextManager.__exit__ suppresses exceptions inside a generator.
	"""

	def __init__(self, run_id: str, name: str, module: int | None, input: Any) -> None:  # noqa: A002
		self._run_id = run_id
		self._name = name
		self._module = module
		self._input = input
		self._span_cm: Any = None
		self._prop_cm: Any = None
		self._root: Any = None

	def __enter__(self) -> Any:
		client = get_langfuse_client()
		if client is None:
			return _NoopObservation()
		try:
			from langfuse import propagate_attributes

			self._span_cm = client.start_as_current_observation(
				name=self._name,
				as_type="span",
				input=self._input,
				metadata={"module": self._module, "run_id": self._run_id},
			)
			self._root = self._span_cm.__enter__()
			self._prop_cm = propagate_attributes(session_id=self._run_id)
			self._prop_cm.__enter__()
			return self._root
		except Exception:
			log.exception("trace_context_enter_failed", run_id=self._run_id)
			return _NoopObservation()

	def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
		if self._prop_cm is not None:
			try:
				self._prop_cm.__exit__(exc_type, exc_val, exc_tb)
			except Exception:
				log.exception("trace_prop_exit_failed", run_id=self._run_id)
		if self._span_cm is not None:
			try:
				self._span_cm.__exit__(exc_type, exc_val, exc_tb)
			except Exception:
				log.exception("trace_span_exit_failed", run_id=self._run_id)


def trace_context(
	run_id: str,
	name: str = "nightout-run",
	module: int | None = None,
	input: Any = None,  # noqa: A002
) -> _TraceContext:
	return _TraceContext(run_id=run_id, name=name, module=module, input=input)


def generation_context(
	name: str,
	model: str,
	input: Any,  # noqa: A002
	model_parameters: dict[str, Any] | None = None,
) -> contextlib.AbstractContextManager[Any]:
	client = get_langfuse_client()
	if client is None:
		return contextlib.nullcontext(enter_result=_NoopObservation())
	try:
		return client.start_as_current_observation(
			name=name, as_type="generation", model=model, input=input, model_parameters=model_parameters or {}
		)
	except Exception:
		log.exception("generation_context_failed", name=name, model=model)
		return contextlib.nullcontext(enter_result=_NoopObservation())


def span_context(name: str, input: Any = None) -> contextlib.AbstractContextManager[Any]:  # noqa: A002
	client = get_langfuse_client()
	if client is None:
		return contextlib.nullcontext(enter_result=_NoopObservation())
	try:
		return client.start_as_current_observation(name=name, as_type="span", input=input)
	except Exception:
		log.exception("span_context_failed", name=name)
		return contextlib.nullcontext(enter_result=_NoopObservation())
