import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import httpx
import redis.asyncio as aioredis

from app.utils.exceptions import PaymentGatewayError
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)

NRB_FOREX_URL = "https://www.nrb.org.np/api/forex/v1/rates"
FOREX_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours

async def _fetch_with_retry(client: httpx.AsyncClient, url: str, params: dict, max_retries: int = 3) -> httpx.Response:
    """Centralized HTTP retry handler that correctly uses last_exception"""
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                return response
            logger.warning(f"[NRB Forex] Attempt {attempt}/{max_retries} returned status code: {response.status_code}")
        except httpx.RequestError as e:
            last_exception = e
            logger.warning(f"[NRB Forex] Attempt {attempt}/{max_retries} network failure: {e}")
        
        if attempt < max_retries:
            await asyncio.sleep(0.5 * attempt)
            
    if last_exception:
        raise last_exception
    raise httpx.HTTPStatusError("Failed to get 200 OK from NRB API", request=None, response=None)


async def convert_to_npr(
    amount: Decimal,
    currency: str,
    redis_client: aioredis.Redis | None = None,
) -> Decimal:
    currency_code = currency.strip().upper()
    if currency_code == "NPR":
        return amount

    cache_key = f"forex:npr_rate:{currency_code}"

    if redis_client is not None:
        try:
            cached_rate = await redis_client.get(cache_key)
            if cached_rate is not None:
                rate_per_unit = Decimal(cached_rate)
                logger.info(f"[NRB Forex] Using cached rate for {currency_code}: {rate_per_unit}")
                return (amount * rate_per_unit).quantize(Decimal("0.01"))
        except Exception as e:
            logger.warning(f"[NRB Forex] Cache read failed, falling back to live API: {e}")

    rate_per_unit = await _fetch_live_rate(currency_code)

    if redis_client is not None:
        try:
            await redis_client.set(cache_key, str(rate_per_unit), ex=FOREX_CACHE_TTL_SECONDS)
        except Exception as e:
            logger.warning(f"[NRB Forex] Failed to write rate to cache: {e}")

    return (amount * rate_per_unit).quantize(Decimal("0.01"))


async def _fetch_live_rate(currency_code: str, max_retries: int = 3) -> Decimal:
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
        try:
            # 1. Try to fetch rates for today using the retry utility
            params = {"page": 1, "per_page": 1, "from": today_str, "to": today_str}
            response = await _fetch_with_retry(client, NRB_FOREX_URL, params, max_retries)
            payload = response.json().get("data", {}).get("payload", [])

            # 2. Fallback to latest available if today's rates aren't published
            if not payload:
                logger.info(f"[NRB Forex] Rates for {today_str} not published yet, fetching latest baseline...")
                fallback_resp = await _fetch_with_retry(client, NRB_FOREX_URL, {"page": 1, "per_page": 1}, max_retries)
                payload = fallback_resp.json().get("data", {}).get("payload", [])

            if not payload or not payload[0].get("rates"):
                raise PaymentGatewayError(internal_detail="Empty payload received from NRB Forex service.")

            rates = payload[0]["rates"]
            target_rate = next(
                (r for r in rates if r.get("currency", {}).get("iso3", "").upper() == currency_code),
                None,
            )

            if target_rate is None:
                raise PaymentGatewayError(internal_detail=f"Currency '{currency_code}' is unsupported by NRB.")

            unit = Decimal(str(target_rate["currency"]["unit"]))
            sell_rate = Decimal(str(target_rate["sell"]))
            rate_per_unit = sell_rate / unit

            logger.info(f"[NRB Forex] Fetched live rate for {currency_code}: {rate_per_unit}")
            return rate_per_unit

        except httpx.RequestError as e:
            logger.error(f"[NRB Forex] Connection exhausted: {e}")
            raise PaymentGatewayError(internal_detail=f"NRB API connection error: {e}") from e
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"[NRB Forex] Extraction mapping crash: {e}")
            raise PaymentGatewayError(internal_detail="Failed to parse exchange rate data from NRB response.") from e
