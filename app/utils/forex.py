import json
from datetime import datetime, timezone
from decimal import Decimal
import httpx
import redis.asyncio as aioredis

from app.utils.exceptions import PaymentGatewayError
from app.utils.logging import LoggerFactory
import asyncio

logger = LoggerFactory.get_logger(__name__)

NRB_FOREX_URL = "https://www.nrb.org.np/api/forex/v1/rates"
FOREX_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours — rates update daily, this is a safe refresh window


async def _fetch_with_retry(client: httpx.AsyncClient, url: str, params: dict, max_retries: int = 3):
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await client.get(url, params=params)
            return response
        except httpx.RequestError as e:
            last_exception = e
            logger.warning(f"[NRB Forex] Attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                await asyncio.sleep(0.5 * attempt)  # 0.5s, 1s, 1.5s backoff
    raise last_exception

async def convert_to_npr(
    amount: Decimal,
    currency: str,
    redis_client: aioredis.Redis | None = None,
) -> Decimal:
    currency_code = currency.strip().upper()
    if currency_code == "NPR":
        return amount

    cache_key = f"forex:npr_rate:{currency_code}"

    # 1. Try cache first
    if redis_client is not None:
        try:
            cached_rate = await redis_client.get(cache_key)
            if cached_rate is not None:
                rate_per_unit = Decimal(cached_rate)
                npr_amount = (amount * rate_per_unit).quantize(Decimal("0.01"))
                logger.info(f"[NRB Forex] Using cached rate for {currency_code}: {rate_per_unit}")
                return npr_amount
        except Exception as e:
            logger.warning(f"[NRB Forex] Cache read failed, falling through to live API: {e}")

    # 2. Cache miss (or no redis) — fetch live, with retry
    rate_per_unit = await _fetch_live_rate(currency_code)

    # 3. Populate cache for next time
    if redis_client is not None:
        try:
            await redis_client.set(cache_key, str(rate_per_unit), ex=FOREX_CACHE_TTL_SECONDS)
        except Exception as e:
            logger.warning(f"[NRB Forex] Failed to write rate to cache: {e}")

    npr_amount = (amount * rate_per_unit).quantize(Decimal("0.01"))
    return npr_amount


async def _fetch_live_rate(currency_code: str, max_retries: int = 3) -> Decimal:
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    last_exception = None

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
        for attempt in range(1, max_retries + 1):
            try:
                payload = []
                params = {"page": 1, "per_page": 1, "from": today_str, "to": today_str}
                response = await client.get(NRB_FOREX_URL, params=params)

                if response.status_code == 200:
                    payload = response.json().get("data", {}).get("payload", [])

                if not payload:
                    logger.info(f"[NRB Forex] Rates for {today_str} not published yet, fetching latest...")
                    fallback_resp = await client.get(NRB_FOREX_URL, params={"page": 1, "per_page": 1})
                    if fallback_resp.status_code == 200:
                        payload = fallback_resp.json().get("data", {}).get("payload", [])

                if not payload or not payload[0].get("rates"):
                    raise PaymentGatewayError(
                        internal_detail="Unable to fetch exchange rates from Nepal Rastra Bank FOREX service."
                    )

                rates = payload[0]["rates"]
                target_rate = next(
                    (r for r in rates if r.get("currency", {}).get("iso3", "").upper() == currency_code),
                    None,
                )

                if target_rate is None:
                    raise PaymentGatewayError(
                        internal_detail=f"Currency '{currency_code}' is not supported by NRB FOREX API."
                    )

                unit = Decimal(str(target_rate["currency"]["unit"]))
                sell_rate = Decimal(str(target_rate["sell"]))
                rate_per_unit = sell_rate / unit

                logger.info(f"[NRB Forex] Fetched live rate for {currency_code}: {rate_per_unit}")
                return rate_per_unit

            except httpx.RequestError as e:
                last_exception = e
                logger.warning(f"[NRB Forex] Attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error(f"[NRB Forex] All {max_retries} attempts failed: {e}")
                raise PaymentGatewayError(
                    internal_detail=f"Network error converting {currency_code} to NPR via NRB FOREX API: {e}"
                ) from e
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"[NRB Forex] Parsing error processing NRB response: {e}")
                raise PaymentGatewayError(
                    internal_detail="Failed to parse exchange rate data from Nepal Rastra Bank."
                ) from e

    raise PaymentGatewayError(internal_detail="Failed to fetch exchange rate after all retries.")
