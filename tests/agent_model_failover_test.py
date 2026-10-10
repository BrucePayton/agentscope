# -*- coding: utf-8 -*-
"""Ordered model failover, including failures at the streaming boundary."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from unittest.async_case import IsolatedAsyncioTestCase

from utils import MockModel
from agentscope.agent import Agent, ModelConfig
from agentscope.model import ChatResponse
from agentscope.message import TextBlock
from agentscope.app.storage import ChatModelConfig


class SlowModel(MockModel):
    """A provider that waits forever before its first response."""

    async def _call_api(self, *args, **kwargs):
        self.cnt += 1
        await asyncio.Event().wait()


class SlowStreamModel(MockModel):
    """A provider that opens a stream but never produces its first chunk."""

    emit_first = False

    async def _call_api(self, *args, **kwargs):
        self.cnt += 1

        async def stream():
            if self.emit_first:
                yield ChatResponse(
                    content=[TextBlock(text="partial")], is_last=False
                )
            await asyncio.Event().wait()
            yield ChatResponse(content=[], is_last=True)

        return stream()


class ModelFailoverTest(IsolatedAsyncioTestCase):
    """Exercise real ChatModelBase cancellation and stream wrappers."""

    async def test_stream_idle_timeout_does_not_replay(self) -> None:
        primary, fallback = SlowStreamModel(), self.success()
        primary.emit_first = True
        stream = await self.agent(
            primary, [fallback], timeout=0.01
        )._call_model([], [])
        self.assertEqual((await anext(stream)).content[0].text, "partial")
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(anext(stream), 1)
        self.assertEqual(fallback.cnt, 0)

    def agent(self, primary, alternatives=(), legacy=None, timeout=None):
        return Agent(
            name="test",
            system_prompt="test",
            model=primary,
            model_config=ModelConfig(
                fallback_models=list(alternatives),
                fallback_model=legacy,
                request_timeout=timeout,
            ),
        )

    def success(self, name="success"):
        return MockModel(
            model=name,
            mock_chat_responses=[
                ChatResponse(content=[TextBlock(text="ok")], is_last=True),
            ],
        )

    async def test_order_and_legacy_fallback(self):
        primary = MockModel(mock_chat_responses=[TimeoutError("first")])
        secondary = MockModel(mock_chat_responses=[TimeoutError("second")])
        legacy = self.success()
        result = await self.agent(primary, [secondary], legacy)._call_model(
            [], []
        )
        self.assertEqual(result.content[0].text, "ok")
        self.assertEqual([primary.cnt, secondary.cnt, legacy.cnt], [1, 1, 1])

    async def test_success_does_not_call_next(self):
        primary, unused = self.success(), self.success()
        await self.agent(primary, [unused])._call_model([], [])
        self.assertEqual(unused.cnt, 0)

    async def test_all_failed_raises_last_error(self):
        models = [
            MockModel(mock_chat_responses=[TimeoutError(str(i))])
            for i in range(3)
        ]
        with self.assertRaisesRegex(TimeoutError, "2"):
            await self.agent(models[0], models[1:])._call_model([], [])
        self.assertEqual([m.cnt for m in models], [1, 1, 1])

    async def test_timeout_even_if_adapter_swallows_cancellation(self):
        for model_cls in (SlowModel, SlowStreamModel):
            with self.subTest(model=model_cls.__name__):
                primary, fallback = model_cls(), self.success()
                result = await asyncio.wait_for(
                    self.agent(primary, [fallback], timeout=0.01)._call_model(
                        [], []
                    ),
                    1,
                )
                self.assertEqual(result.content[0].text, "ok")
                self.assertEqual(fallback.cnt, 1)

    async def test_first_stream_error_switches(self):
        primary = MockModel(
            mock_chat_responses=[[TimeoutError("first chunk")]]
        )
        fallback = self.success()
        result = await self.agent(primary, [fallback])._call_model([], [])
        self.assertEqual(result.content[0].text, "ok")

    async def test_partial_stream_not_replayed(self):
        primary = MockModel(
            mock_chat_responses=[
                [
                    ChatResponse(
                        content=[TextBlock(text="partial")], is_last=False
                    ),
                    TimeoutError("interrupted stream"),
                ]
            ]
        )
        fallback = self.success()
        stream = await self.agent(primary, [fallback])._call_model([], [])
        self.assertEqual((await anext(stream)).content[0].text, "partial")
        with self.assertRaises(TimeoutError):
            await anext(stream)
        self.assertEqual(fallback.cnt, 0)

    async def test_cancel_does_not_switch(self):
        primary, fallback = SlowModel(), self.success()
        task = asyncio.create_task(
            self.agent(primary, [fallback], timeout=10)._call_model([], [])
        )
        while not primary.cnt:
            await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(fallback.cnt, 0)

    def test_config_validation_and_roundtrip(self):
        config = ChatModelConfig(
            type="test",
            credential_id="id",
            model="primary",
            parameters={},
            fallback_models=[" second ", "second", "third"],
            request_timeout=60,
        )
        self.assertEqual(config.fallback_models, ["second", "third"])
        self.assertEqual(
            ChatModelConfig.model_validate_json(config.model_dump_json()),
            config,
        )
        for update in (
            {"fallback_models": [" "]},
            {"request_timeout": 0},
            {"request_timeout": float("inf")},
        ):
            with self.assertRaises(ValueError):
                ChatModelConfig.model_validate(
                    {**config.model_dump(), **update}
                )

    def test_catalogue_order_and_deduplication(self) -> None:
        from agentscope.app._service._model import get_fallback_names

        config = ChatModelConfig(
            type="test",
            credential_id="id",
            model="primary",
            parameters={},
            fallback_models=["manual", "primary"],
            fallback_from_catalog=True,
        )
        cards = [
            SimpleNamespace(name=n)
            for n in ["primary", "second", "manual", "third", "second"]
        ]
        with patch.object(MockModel, "list_models", return_value=cards):
            self.assertEqual(
                get_fallback_names(config, MockModel()),
                ["manual", "second", "third"],
            )
            config.fallback_from_catalog = False
            self.assertEqual(
                get_fallback_names(config, MockModel()), ["manual"]
            )
