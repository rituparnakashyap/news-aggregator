# Import strategies so their @register decorators fire at import time
from news_aggregator.aggregation import top_n, top_n_lucky_m  # noqa: F401
