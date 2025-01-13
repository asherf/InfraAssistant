from typing import AsyncGenerator

import pytest

from assistant.logic.helpers import StreamTagExtractor


@pytest.fixture
def on_message_callback():
    async def callback(stream: AsyncGenerator[str, None]):
        async for token in stream:
            callback.messages.append(token)

    callback.messages = []
    return callback


@pytest.fixture
def on_tag_callback():
    def callback(tag_name, tag_content):
        callback.tags.append((tag_name, tag_content))

    callback.tags = []
    return callback


@pytest.fixture
def stream_tag_extractor(on_message_callback, on_tag_callback):
    return StreamTagExtractor(on_message_callback, on_tag_callback)


class TestStreamTagExtractor:
    @pytest.mark.asyncio
    async def test_handle_token_normal_text(self, stream_tag_extractor, on_message_callback):
        await stream_tag_extractor.handle_token("Hello World")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == ["Hello World"]

    @pytest.mark.asyncio
    async def test_handle_token_single_tag(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        await stream_tag_extractor.handle_token("<tag>content</tag>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == []
        assert on_tag_callback.tags == [("tag", "<tag>content</tag>")]

    @pytest.mark.asyncio
    async def test_handle_token_mixed_content(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        await stream_tag_extractor.handle_token("Hello <tag>content</tag> World")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == ["Hello ", " World"]
        assert on_tag_callback.tags == [("tag", "<tag>content</tag>")]

    @pytest.mark.asyncio
    async def test_handle_token_multiple_tags(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        await stream_tag_extractor.handle_token("<tag1>content1</tag1><tag2>content2</tag2>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == []
        assert on_tag_callback.tags == [("tag1", "<tag1>content1</tag1>"), ("tag2", "<tag2>content2</tag2>")]

    @pytest.mark.asyncio
    async def test_handle_token_text_before_tag(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        await stream_tag_extractor.handle_token("Text before <tag>content</tag>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == ["Text before "]
        assert on_tag_callback.tags == [("tag", "<tag>content</tag>")]

    @pytest.mark.asyncio
    async def test_handle_token_text_after_tag(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        await stream_tag_extractor.handle_token("<tag>content</tag> Text after")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == [" Text after"]
        assert on_tag_callback.tags == [("tag", "<tag>content</tag>")]

    @pytest.mark.asyncio
    async def test_handle_token_text_between_tags(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        await stream_tag_extractor.handle_token("<tag1>content1</tag1> Text between <tag2>content2</tag2>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == [" Text between "]
        assert on_tag_callback.tags == [("tag1", "<tag1>content1</tag1>"), ("tag2", "<tag2>content2</tag2>")]

    @pytest.mark.asyncio
    async def test_handle_token_empty_tag(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        await stream_tag_extractor.handle_token("<tag></tag>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == []
        assert on_tag_callback.tags == [("tag", "<tag></tag>")]

    @pytest.mark.skip(reason="Not supported yet")
    @pytest.mark.asyncio
    async def test_handle_token_nested_tags(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        await stream_tag_extractor.handle_token("<outer><inner>content</inner></outer>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == []
        assert on_tag_callback.tags == [("outer", "<outer><inner>content</inner></outer>")]

    @pytest.mark.skip(reason="Not supported yet")
    @pytest.mark.asyncio
    async def test_handle_token_incomplete_tag(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        await stream_tag_extractor.handle_token("<tag>content")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == []
        assert on_tag_callback.tags == []
