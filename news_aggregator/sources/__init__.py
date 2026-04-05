# Import all adapters so their @register decorators fire at import time
from news_aggregator.sources import gdelt, guardian, newsapi  # noqa: F401
