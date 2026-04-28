"""Entry point:
  python -m quantgpt --transport http --port 8003
  python -m quantgpt --prefetch hs300 csi500
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Load .env from project root
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.is_file():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


def prefetch(universes: list[str]):
    """Pre-download market data for given universes."""
    from .market_data import MarketDataFetcher, fetch_benchmark_returns, get_universe

    fetcher = MarketDataFetcher()
    for name in universes:
        logger.info(f"Prefetching universe: {name}")
        codes = get_universe(name)
        logger.info(f"  {len(codes)} stocks, fetching data...")
        df = fetcher.fetch_stocks(codes, "2020-01-01", "2025-12-31")
        if df is not None:
            logger.info(f"  Done: {len(df):,} records cached")
        else:
            logger.warning(f"  No data fetched for {name}")

    for bm in ("hs300", "zz500"):
        logger.info(f"Prefetching benchmark: {bm}")
        fetch_benchmark_returns(bm, "2020-01-01", "2025-12-31")

    logger.info("Prefetch complete.")


def main():
    parser = argparse.ArgumentParser(description="QuantGPT Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http", "http"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--prefetch", nargs="+", metavar="UNIVERSE", help="Pre-download data: hs300 csi500 small_scale")
    args = parser.parse_args()

    if args.prefetch:
        prefetch(args.prefetch)
        return

    if args.transport == "http":
        import uvicorn

        from .api_server import app
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        from .mcp_server import mcp
        if args.transport in ("sse", "streamable-http"):
            os.environ.setdefault("FASTMCP_HOST", args.host)
            os.environ.setdefault("FASTMCP_PORT", str(args.port))
        mcp.run(transport=args.transport)


main()
