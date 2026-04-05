# news-aggregator

LLM-powered, config-driven news aggregator. Fetches articles from multiple free sources, deduplicates and ranks them by mention frequency, then uses an LLM to produce a short headline and multi-line summary per category.

## Quickstart

```bash
# 1. Clone and install
git clone <repo-url> && cd news-aggregator
pip install -e ".[dev]"

# 2. Set up secrets
cp .env.example .env
# Edit .env and fill in your API keys

# 3. Validate config
news-aggregator validate-config --config config/default.yaml

# 4. Run
news-aggregator run --config config/default.yaml
news-aggregator run --output-format markdown
news-aggregator run --output-format json --output-file digest.json
news-aggregator run --lookback-hours 48
```

## Free API Keys

| Source | Sign up | Free tier |
|---|---|---|
| [NewsAPI](https://newsapi.org) | newsapi.org | 100 req/day |
| [The Guardian](https://open-platform.theguardian.com) | open-platform.theguardian.com | 500 req/day |
| GDELT | *(no key required)* | Unlimited |

## Config Reference

`config/default.yaml`:

| Key | Type | Default | Description |
|---|---|---|---|
| `sources[].name` | string | — | `newsapi`, `guardian`, or `gdelt` |
| `sources[].enabled` | bool | `true` | Disable a source without removing it |
| `categories[].name` | string | — | Category name (e.g. `technology`) |
| `categories[].sources` | list | global | Override source list for this category |
| `categories[].strategy` | string | global | Override strategy for this category |
| `categories[].strategy_params` | dict | global | Override strategy params for this category |
| `aggregation.strategy` | string | `TopN` | Global aggregation strategy |
| `aggregation.params.n` | int | `5` | Number of articles to return (TopN / TopNLuckyM) |
| `aggregation.params.m` | int | — | Lucky slots for TopNLuckyM |
| `aggregation.lookback_hours` | int | `24` | How far back to fetch articles (1–168) |
| `aggregation.dedup_threshold` | float | `0.85` | Jaccard similarity threshold for near-duplicate merging |
| `llm.model` | string | `${LLM_MODEL}` | LLM model name |
| `llm.headline_max_chars` | int | `100` | Max characters for generated headline (A) |
| `llm.summary_max_lines` | int | `3` | Lines in generated summary (B) |
| `llm.temperature` | float | `0.3` | LLM temperature |
| `output_format` | string | `text` | `text`, `json`, or `markdown` |

## Environment Variables (`.env`)

```
LLM_API_KEY=         # Required: your LLM API key
LLM_BASE_URL=        # OpenAI-compatible endpoint (default: https://api.openai.com/v1)
LLM_MODEL=           # Model name (e.g. gpt-4o-mini, llama3, claude-3-5-sonnet)
NEWSAPI_KEY=         # Required if newsapi source is enabled
GUARDIAN_KEY=        # Required if guardian source is enabled
```

The LLM client uses the `openai` package with a configurable `base_url`, so it works with **OpenAI, Ollama, Groq, LM Studio, Anthropic-compatible endpoints**, and more.

## Aggregation Strategies

| Strategy | Params | Description |
|---|---|---|
| `TopN` | `n` | Return top N articles by mention count |
| `TopNLuckyM` | `n`, `m` | Top N, but replace M slots with random picks from lower-ranked articles |

## Adding a New News Source

1. Create `news_aggregator/sources/mysource.py`
2. Subclass `BaseNewsSource`, set `name = "mysource"`
3. Decorate the class with `@register`
4. Implement `fetch()` and `_normalize()`
5. Import in `news_aggregator/sources/__init__.py`

No other changes needed — the registry handles discovery automatically.

## Adding a New Strategy

1. Create `news_aggregator/aggregation/mystrategy.py`
2. Subclass `BaseStrategy`, set `name = "MyStrategy"`, implement `select()`
3. Import in `news_aggregator/aggregation/__init__.py`

## CLI Commands

```
news-aggregator run              # Fetch and summarise news
news-aggregator validate-config  # Check config without fetching
news-aggregator list-sources     # Show registered source adapters
```

## Development

```bash
make install   # pip install -e ".[dev]"
make test      # pytest with coverage
make lint      # ruff + mypy
make run       # news-aggregator run --config config/default.yaml
```
