import re


def to_unicode_bold(text: str) -> str:
    """Convert ASCII alphanumeric characters to Unicode Mathematical Sans-Serif Bold (A-Z, a-z, 0-9)."""
    res = []
    for c in text:
        code = ord(c)
        if 65 <= code <= 90:  # A-Z -> Sans-Serif Bold
            res.append(chr(0x1D5D4 + code - 65))
        elif 97 <= code <= 122:  # a-z -> Sans-Serif Bold
            res.append(chr(0x1D5EE + code - 97))
        elif 48 <= code <= 57:  # 0-9 -> Sans-Serif Bold
            res.append(chr(0x1D7CE + code - 48))
        else:
            res.append(c)
    return "".join(res)


def is_pure_ascii(text: str) -> bool:
    """Check whether text consists exclusively of ASCII characters."""
    return all(ord(c) < 128 for c in text)


def clean_facebook_post_text(text: str) -> str:
    """Format markdown-styled text into clean, high-engagement Facebook post format.

    - Replaces markdown links [Title](URL) with direct URL references.
    - Strips markdown heading symbols (#, ##, ###) while preserving emojis and text.
    - Preserves #hashtags at line start or anywhere in the post.
    - Removes markdown horizontal divider rules (---, ***, ___).
    - Converts pure-ASCII bold (**text**) into Unicode Sans-Serif bold.
    - Strips bold/italic markers (*, **, _) from non-ASCII/Vietnamese text cleanly.
    - Strips backticks from inline code blocks.
    - Normalizes spacing.
    """
    if not text:
        return ""

    # 1. Convert markdown links [Label](url) -> direct url or Label: url
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        lambda m: (
            m.group(2)
            if m.group(1).lower()
            in ("link", "url", "read here", "here", "arxiv link", "paper")
            else f"{m.group(1)}: {m.group(2)}"
        ),
        text,
    )

    # 2. Remove markdown header symbols (#, ##, ###, ####) at line start (require trailing whitespace to preserve #hashtags)
    text = re.sub(r"^[ \t]*#{1,6}\s+", "", text, flags=re.MULTILINE)

    # 3. Remove horizontal rules (---, ***, ___)
    text = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", "", text, flags=re.MULTILINE)

    # 4. Handle bold **text**
    def replace_bold(match: re.Match) -> str:
        content = match.group(1).strip()
        if not content:
            return ""
        if is_pure_ascii(content):
            return to_unicode_bold(content)
        return content

    text = re.sub(r"\*\*([^*]+)\*\*", replace_bold, text)

    # 5. Handle italic *text* and _text_
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"\1", text)

    # 6. Remove inline code backticks `code` -> code
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # 7. Normalize multiple empty lines to at most 2 newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
