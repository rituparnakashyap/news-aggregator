from __future__ import annotations

from news_aggregator.models.article import Article

_SYSTEM_PROMPT = """\
You are a professional news editor. Your job is to synthesize a set of related news articles \
into a single concise headline and a list of per-story summary sentences.

Rules:
- Respond ONLY with a JSON object: {{"headline": "...", "summaries": ["...", "...", ...]}}
- The headline MUST be under {headline_max_chars} characters.
- summaries MUST be a JSON array of exactly {summary_max_lines} strings, \
one complete sentence per top story.
- Do not add any text outside the JSON object.
- Be factual and neutral. Do not add opinions or speculation."""


def build_prompt(
    articles: list[Article],
    headline_max_chars: int,
    summary_max_lines: int,
) -> list[dict]:
    """Build the OpenAI messages list for headline + summary generation."""
    system = _SYSTEM_PROMPT.format(
        headline_max_chars=headline_max_chars,
        summary_max_lines=summary_max_lines,
    )

    # Use up to 5 articles to keep token usage bounded
    top_articles = articles[:5]
    article_lines = []
    for i, article in enumerate(top_articles, start=1):
        snippet = article.content_snippet or article.description or article.title
        article_lines.append(f"{i}. Title: {article.title}\n   Summary: {snippet}")

    articles_text = "\n\n".join(article_lines)
    user_message = (
        f"Here are the top news articles for this category:\n\n"
        f"{articles_text}\n\n"
        f"Please provide a synthesized headline (under {headline_max_chars} characters) "
        f"and exactly {summary_max_lines} summary sentence(s) — one per top story."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message},
    ]
