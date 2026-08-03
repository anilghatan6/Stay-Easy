import httpx
from decimal import Decimal
from app.modules.booking.payment.base_strategy import PaymentStrategy
from app.utils.exceptions import PaymentGatewayError
from app.utils.logging import LoggerFactory
from typing import Optional
from app.utils.forex import convert_to_npr

logger = LoggerFactory.get_logger(__name__)

KHALTI_INITIATE_URL = "https://a.khalti.com/api/v2/epayment/initiate/"
KHALTI_LOOKUP_URL = "https://a.khalti.com/api/v2/epayment/lookup/"


class KhaltiPaymentStrategy(PaymentStrategy):
    def __init__(self, secret_key: str,  website_url: str, redis_client=None):
        if not secret_key:
            raise PaymentGatewayError("Khalti secret key is not configured")
        self.secret_key = secret_key
        self.website_url = website_url
        self.headers = {
            "Authorization": f"Key {self.secret_key}",
            "Content-Type": "application/json",
        }
        self.redis_client = redis_client

    async def create_payment_intent(self, ref_number: str, amount: Decimal, currency: str,return_url: Optional[str] = None) -> dict:
        if currency.upper() != "NPR":

            try:
                amount_npr = await convert_to_npr(amount, currency, redis_client=self.redis_client)
                logger.warning(f"[KhaltiStrategy] Converted amount {amount} {currency} to {amount_npr} NPR")
            except PaymentGatewayError:
                raise   
        else:
            amount_npr = amount

        amount_paisa = int(amount_npr * 100)  # Decimal rupees -> integer paisa

        payload = {
            "return_url": return_url,
            "website_url": self.website_url,
            "amount": amount_paisa,
            "purchase_order_id": ref_number,
            "purchase_order_name": f"Booking {ref_number}",
        }

        logger.info(f"[KhaltiStrategy] Initiating payment for {ref_number}")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(KHALTI_INITIATE_URL, json=payload, headers=self.headers)

            if response.status_code != 200:
                logger.error(f"[KhaltiStrategy] Initiate failed for {ref_number}: {response.text}")
                raise PaymentGatewayError(internal_detail=f"Khalti initiate failed: {response.text}")

            data = response.json()
            return {
                "payment_intent_id": data["pidx"],
                "payment_url": data["payment_url"],
            }
        except Exception as e:
            logger.error(f"[KhaltiStrategy] Initiate failed for {ref_number}: {e}")
            raise PaymentGatewayError(internal_detail=f"Khalti initiate failed: {e}")
        
    async def verify_payment(self, ref_number: str, gateway_payload: dict) -> bool:
        pidx = gateway_payload.get("pidx") or gateway_payload.get("payment_intent_id")
        if not pidx:
            logger.error(f"[KhaltiStrategy] Missing pidx for {ref_number}")
            return False

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    KHALTI_LOOKUP_URL, json={"pidx": pidx}, headers=self.headers
                )

            if response.status_code != 200:
                logger.error(f"[KhaltiStrategy] Lookup failed for {ref_number}: {response.text}")
                return False

            data = response.json()
            logger.info(f"[KhaltiStrategy] Verification response for {ref_number}: {data}")
            return data.get("status") == "Completed"

        except httpx.RequestError as e:
            logger.error(f"[KhaltiStrategy] Network error verifying payment for {ref_number}: {e}")
            return False  # fail closed — never confirm on a network error
        except ValueError as e:
            logger.error(f"[KhaltiStrategy] Invalid JSON response verifying {ref_number}: {e}")
            return False

    async def refund(self, ref_number: str, gateway_payload: dict, amount: Decimal | None = None) -> dict:
        # Khalti does not expose a public refund API for merchants as of this integration —
        # refunds must be processed manually through the Khalti merchant dashboard.
        logger.warning(f"[KhaltiStrategy] Refund requested for {ref_number} — not supported via API")
        raise PaymentGatewayError(
            internal_detail="Khalti refunds must be processed manually through the Khalti merchant dashboard."
        )

    async def cancel_intent(self, ref_number: str, intent_id: str) -> None:
        # Khalti has no cancel-intent concept — an un-completed pidx simply expires unused
        logger.info(f"[KhaltiStrategy] No-op cancel for pidx {intent_id}")
