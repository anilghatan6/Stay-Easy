import httpx
from decimal import Decimal
from app.modules.booking.payment.base_strategy import PaymentStrategy
from app.utils.exceptions import PaymentGatewayError
from app.utils.logging import LoggerFactory
from typing import Optional
from app.utils.forex import convert_to_npr

logger = LoggerFactory.get_logger(__name__)

KHALTI_BASE_URL = "https://a.khalti.com"
KHALTI_INITIATE_URL = f"{KHALTI_BASE_URL}/api/v2/epayment/initiate/"
KHALTI_LOOKUP_URL = f"{KHALTI_BASE_URL}/api/v2/epayment/lookup/"


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

            # Store transaction_id in gateway_payload for future refunds
            if data.get("transaction_id"):
                gateway_payload["transaction_id"] = data["transaction_id"]

            return data.get("status") == "Completed"

        except httpx.RequestError as e:
            logger.error(f"[KhaltiStrategy] Network error verifying payment for {ref_number}: {e}")
            return False  # fail closed — never confirm on a network error
        except ValueError as e:
            logger.error(f"[KhaltiStrategy] Invalid JSON response verifying {ref_number}: {e}")
            return False

    async def refund(self, ref_number: str, gateway_payload: dict, amount: Decimal | None = None) -> dict:
        pidx = gateway_payload.get("pidx") or gateway_payload.get("payment_intent_id")
        transaction_id = gateway_payload.get("transaction_id")

        if not pidx and not transaction_id:
            raise PaymentGatewayError(
                internal_detail="Khalti refund failed: no pidx or transaction_id in gateway_payload"
            )

        # Resolve transaction_id via lookup if not already stored
        if not transaction_id:
            logger.info(f"[KhaltiStrategy] Resolving transaction_id via lookup for {ref_number}")
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        KHALTI_LOOKUP_URL, json={"pidx": pidx}, headers=self.headers
                    )
                if response.status_code != 200:
                    raise PaymentGatewayError(
                        internal_detail=f"Khalti lookup failed for refund: {response.text}"
                    )
                data = response.json()
                transaction_id = data.get("transaction_id")
                if not transaction_id:
                    raise PaymentGatewayError(
                        internal_detail=f"Khalti lookup returned no transaction_id for {ref_number}"
                    )
            except PaymentGatewayError:
                raise
            except Exception as e:
                raise PaymentGatewayError(
                    internal_detail=f"Khalti lookup error for refund: {e}"
                )

        # Build refund payload — amount in paisa, full refund if amount is None
        refund_payload = {}
        if amount is not None:
            amount_paisa = int(amount * 100)
            refund_payload["amount"] = amount_paisa

        logger.info(f"[KhaltiStrategy] Processing refund for {ref_number} (txn: {transaction_id}, payload: {refund_payload})")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{KHALTI_BASE_URL}/api/merchant-transaction/{transaction_id}/refund/",
                    json=refund_payload,
                    headers=self.headers,
                )

            if response.status_code not in (200, 201):
                logger.error(f"[KhaltiStrategy] Refund failed for {ref_number}: {response.text}")
                raise PaymentGatewayError(
                    internal_detail=f"Khalti refund failed: {response.text}"
                )

            data = response.json()
            logger.info(f"[KhaltiStrategy] Refund successful for {ref_number}: {data}")
            return {"status": "refunded", "detail": data.get("detail", "Refund processed")}

        except PaymentGatewayError:
            raise
        except httpx.RequestError as e:
            logger.error(f"[KhaltiStrategy] Network error processing refund for {ref_number}: {e}")
            raise PaymentGatewayError(
                internal_detail=f"Khalti refund network error: {e}"
            )
        except Exception as e:
            logger.error(f"[KhaltiStrategy] Unexpected error processing refund for {ref_number}: {e}")
            raise PaymentGatewayError(
                internal_detail=f"Khalti refund error: {e}"
            )

    async def cancel_intent(self, ref_number: str, intent_id: str) -> None:
        # Khalti has no cancel-intent concept — an un-completed pidx simply expires unused
        logger.info(f"[KhaltiStrategy] No-op cancel for pidx {intent_id}")
