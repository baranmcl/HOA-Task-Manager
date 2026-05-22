from apps.projects.markdown_utils import render_note


def test_basic_paragraph():
    out = render_note("Hello world")
    assert "<p>Hello world</p>" in out


def test_bold_and_italic():
    out = render_note("**bold** and *italic*")
    assert "<strong>bold</strong>" in out
    assert "<em>italic</em>" in out


def test_link_preserved():
    out = render_note("See [docs](https://example.com)")
    assert 'href="https://example.com"' in out


def test_script_stripped():
    out = render_note("<script>alert(1)</script>Hello")
    assert "<script>" not in out


def test_disallowed_tag_stripped():
    out = render_note('<iframe src="https://evil"></iframe>safe')
    assert "<iframe" not in out
    assert "safe" in out


def test_no_javascript_url():
    out = render_note('[click](javascript:alert(1))')
    assert "javascript:" not in out
