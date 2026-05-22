import bleach
import markdown as md

ALLOWED_TAGS = [
    "p", "br", "strong", "em", "u", "code", "pre",
    "ul", "ol", "li", "blockquote",
    "a", "h2", "h3", "h4",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def render_note(raw: str) -> str:
    """Render markdown to safe HTML for an UpdateNote body."""
    rendered = md.markdown(raw, extensions=["extra"])
    return bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
