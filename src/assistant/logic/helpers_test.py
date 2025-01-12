import pytest

from assistant.logic.helpers import StreamTagExtractor


@pytest.fixture
def on_message_callback():
    def callback(message):
        callback.messages.append(message)

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
    def test_handle_token_normal_text(self, stream_tag_extractor, on_message_callback):
        stream_tag_extractor.handle_token("Hello World")
        assert on_message_callback.messages == ["Hello World"]

    def test_handle_token_single_tag(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        stream_tag_extractor.handle_token("<tag>content</tag>")
        assert on_message_callback.messages == []
        assert on_tag_callback.tags == [("tag", "<tag>content</tag>")]

    def test_handle_token_mixed_content(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        stream_tag_extractor.handle_token("Hello <tag>content</tag> World")
        assert on_message_callback.messages == ["Hello ", " World"]
        assert on_tag_callback.tags == [("tag", "<tag>content</tag>")]

    def test_handle_token_nested_tags(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        stream_tag_extractor.handle_token("<outer><inner>content</inner></outer>")
        assert on_message_callback.messages == []
        assert on_tag_callback.tags == [("outer", "<outer><inner>content</inner></outer>")]

    def test_handle_token_incomplete_tag(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        stream_tag_extractor.handle_token("<tag>content")
        assert on_message_callback.messages == []
        assert on_tag_callback.tags == []

    def test_handle_token_multiple_tags(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        stream_tag_extractor.handle_token("<tag1>content1</tag1><tag2>content2</tag2>")
        assert on_message_callback.messages == []
        assert on_tag_callback.tags == [("tag1", "<tag1>content1</tag1>"), ("tag2", "<tag2>content2</tag2>")]

    def test_handle_token_text_before_tag(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        stream_tag_extractor.handle_token("Text before <tag>content</tag>")
        assert on_message_callback.messages == ["Text before "]
        assert on_tag_callback.tags == [("tag", "<tag>content</tag>")]

    def test_handle_token_text_after_tag(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        stream_tag_extractor.handle_token("<tag>content</tag> Text after")
        assert on_message_callback.messages == [" Text after"]
        assert on_tag_callback.tags == [("tag", "<tag>content</tag>")]

    def test_handle_token_text_between_tags(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        stream_tag_extractor.handle_token("<tag1>content1</tag1> Text between <tag2>content2</tag2>")
        assert on_message_callback.messages == [" Text between "]
        assert on_tag_callback.tags == [("tag1", "<tag1>content1</tag1>"), ("tag2", "<tag2>content2</tag2>")]

    def test_handle_token_empty_tag(self, stream_tag_extractor, on_message_callback, on_tag_callback):
        stream_tag_extractor.handle_token("<tag></tag>")
        assert on_message_callback.messages == []
        assert on_tag_callback.tags == [("tag", "<tag></tag>")]
