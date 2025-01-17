from collections import defaultdict
from collections.abc import AsyncGenerator

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
def on_tag_start_callback():
    async def callback(tag_name: str, stream: AsyncGenerator[str, None]):
        async for token in stream:
            callback.tags[tag_name].append(token)

    callback.tags = defaultdict(list)
    return callback


@pytest.fixture
def stream_tag_extractor(on_message_callback, on_tag_callback, on_tag_start_callback) -> StreamTagExtractor:
    return StreamTagExtractor(
        on_message_callback=on_message_callback,
        on_tag_callback=on_tag_callback,
        on_tag_start_callback=on_tag_start_callback,
    )


def assert_tags(expected_tags: list[tuple[str, str]], actual_tags: list[tuple[str, str]], tags_stream_dict) -> None:
    assert expected_tags == actual_tags
    stream_tags = {tag: "".join(parts) for tag, parts in tags_stream_dict.items()}
    assert stream_tags == dict(expected_tags)


class TestStreamTagExtractor:
    @pytest.mark.asyncio
    async def test_handle_token_normal_text(
        self,
        stream_tag_extractor,
        on_message_callback,
        on_tag_callback,
        on_tag_start_callback,
    ) -> None:
        await stream_tag_extractor.handle_token("Hello World")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == ["Hello World"]
        assert_tags([], on_tag_callback.tags, on_tag_start_callback.tags)

    @pytest.mark.asyncio
    async def test_handle_token_single_tag(
        self,
        stream_tag_extractor,
        on_message_callback,
        on_tag_callback,
        on_tag_start_callback,
    ) -> None:
        await stream_tag_extractor.handle_token("<tag>content</tag>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == []
        assert_tags([("tag", "<tag>content</tag>")], on_tag_callback.tags, on_tag_start_callback.tags)

    @pytest.mark.asyncio
    async def test_handle_token_mixed_content(
        self,
        stream_tag_extractor,
        on_message_callback,
        on_tag_callback,
        on_tag_start_callback,
    ) -> None:
        await stream_tag_extractor.handle_token("Hello <tag>content</tag> World")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == ["Hello ", " World"]
        assert_tags([("tag", "<tag>content</tag>")], on_tag_callback.tags, on_tag_start_callback.tags)

    @pytest.mark.asyncio
    async def test_handle_token_multiple_tags(
        self,
        stream_tag_extractor,
        on_message_callback,
        on_tag_callback,
        on_tag_start_callback,
    ) -> None:
        await stream_tag_extractor.handle_token("<tag1>content1</tag1><tag2>content2</tag2>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == []
        assert_tags(
            [("tag1", "<tag1>content1</tag1>"), ("tag2", "<tag2>content2</tag2>")],
            on_tag_callback.tags,
            on_tag_start_callback.tags,
        )

    @pytest.mark.asyncio
    async def test_handle_token_text_before_tag(
        self,
        stream_tag_extractor,
        on_message_callback,
        on_tag_callback,
        on_tag_start_callback,
    ) -> None:
        await stream_tag_extractor.handle_token("Text before <tag>content</tag>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == ["Text before "]
        assert_tags([("tag", "<tag>content</tag>")], on_tag_callback.tags, on_tag_start_callback.tags)

    @pytest.mark.asyncio
    async def test_handle_token_text_after_tag(
        self,
        stream_tag_extractor,
        on_message_callback,
        on_tag_callback,
        on_tag_start_callback,
    ) -> None:
        await stream_tag_extractor.handle_token("<tag>content</tag> Text after")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == [" Text after"]
        assert_tags([("tag", "<tag>content</tag>")], on_tag_callback.tags, on_tag_start_callback.tags)

    @pytest.mark.asyncio
    async def test_handle_token_text_between_tags(
        self,
        stream_tag_extractor,
        on_message_callback,
        on_tag_callback,
        on_tag_start_callback,
    ) -> None:
        await stream_tag_extractor.handle_token("<tag1>content1</tag1> Text between <tag2>content2</tag2>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == [" Text between "]
        assert_tags(
            [("tag1", "<tag1>content1</tag1>"), ("tag2", "<tag2>content2</tag2>")],
            on_tag_callback.tags,
            on_tag_start_callback.tags,
        )

    @pytest.mark.asyncio
    async def test_handle_token_empty_tag(
        self,
        stream_tag_extractor,
        on_message_callback,
        on_tag_callback,
        on_tag_start_callback,
    ) -> None:
        await stream_tag_extractor.handle_token("<tag></tag>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == []
        assert_tags([("tag", "<tag></tag>")], on_tag_callback.tags, on_tag_start_callback.tags)

    @pytest.mark.skip(reason="Not supported yet")
    @pytest.mark.asyncio
    async def test_handle_token_nested_tags(
        self,
        stream_tag_extractor,
        on_message_callback,
        on_tag_callback,
        on_tag_start_callback,
    ) -> None:
        await stream_tag_extractor.handle_token("<outer><inner>content</inner></outer>")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == []
        assert_tags(
            [("outer", "<outer><inner>content</inner></outer>")],
            on_tag_callback.tags,
            on_tag_start_callback.tags,
        )

    @pytest.mark.skip(reason="Not supported yet")
    @pytest.mark.asyncio
    async def test_handle_token_incomplete_tag(
        self,
        stream_tag_extractor,
        on_message_callback,
        on_tag_callback,
        on_tag_start_callback,
    ) -> None:
        await stream_tag_extractor.handle_token("<tag>content")
        await stream_tag_extractor.wait_for_tasks()
        assert on_message_callback.messages == []
        assert_tags([], on_tag_callback.tags, on_tag_start_callback.tags)
