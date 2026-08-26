import hmac
import hashlib
import base64
import uuid
import httpx
from decimal import Decimal

from app.modules.booking.payment.base_strategy import PaymentStrategy
from app.utils.exceptions import PaymentGatewayError
from app.utils.logging import LoggerFactory
from app.utils.forex import convert_to_npr

logger = LoggerFactory.get_logger(__name__)

ESEWA_FORM_URL = "https://rc-epay.esewa.com.np/api/epay/main/v2/form"  # test/sandbox
ESEWA_STATUS_URL = "https://rc.esewa.com.np/api/epay/transaction/status/"  # test/sandbox
# Production equivalents: https://epay.esewa.com.np/... and https://epay.esewa.com.np/api/epay/transaction/status/


class EsewaPaymentStrategy(PaymentStrategy):
    def __init__(self, product_code: str, secret_key: str, redis_client=None):
        if not product_code or not secret_key:
            raise PaymentGatewayError("eSewa product_code/secret_key is not configured")
        self.product_code = product_code
        self.secret_key = secret_key
        self.redis_client = redis_client

    def _generate_signature(self, total_amount: str, transaction_uuid: str) -> str:
        """
        eSewa requires an HMAC-SHA256 signature over a specific message format,
        base64-encoded. Field order and names must match exactly what's declared
        in signed_field_names.
        """
        message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={self.product_code}"
        digest = hmac.new(
            self.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    async def create_payment_intent(
        self, ref_number: str, amount: Decimal, currency: str, return_url: str = None
    ) -> dict:
        if currency.upper() != "NPR":
            try:
                amount_npr = await convert_to_npr(amount, currency, redis_client=self.redis_client)
                logger.warning(f"[EsewaStrategy] Converted amount {amount} {currency} to {amount_npr} NPR")
            except PaymentGatewayError:
                raise
        else:
            amount_npr = amount

        # eSewa requires its own unique transaction id per attempt
        transaction_uuid = f"{ref_number}-{uuid.uuid4().hex[:8]}"
        total_amount = f"{amount_npr:.2f}"

        signature = self._generate_signature(total_amount, transaction_uuid)

        success_url = return_url or ""
        failure_url = return_url or ""

        form_fields = {
            "amount": total_amount,
            "tax_amount": "0",
            "total_amount": total_amount,
            "transaction_uuid": transaction_uuid,
            "product_code": self.product_code,
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "success_url": success_url,
            "failure_url": failure_url,
            "signed_field_names": "total_amount,transaction_uuid,product_code",
            "signature": signature,
        }

        logger.info(f"[EsewaStrategy] Prepared payment form for {ref_number} (txn: {transaction_uuid})")

        return {
            "payment_intent_id": transaction_uuid,
            "form_url": ESEWA_FORM_URL,
            "form_fields": form_fields,
        }

    async def verify_payment(self, ref_number: str, gateway_payload: dict) -> bool:
        if "data" in gateway_payload:
            import json
            import base64
            try:
                decoded_data = base64.b64decode(gateway_payload["data"]).decode("utf-8")
                esewa_data = json.loads(decoded_data)
                gateway_payload.update(esewa_data)
            except Exception as e:
                logger.error(f"[EsewaStrategy] Failed to decode eSewa data parameter for {ref_number}: {e}")
                return False

        transaction_uuid = gateway_payload.get("transaction_uuid") or gateway_payload.get("payment_intent_id")
        total_amount = gateway_payload.get("total_amount")

        if not transaction_uuid or not total_amount:
            logger.error(f"[EsewaStrategy] Missing transaction_uuid/total_amount for {ref_number}")
            return False
            
        total_amount_str = str(total_amount).replace(",", "")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    ESEWA_STATUS_URL,
                    params={
                        "product_code": self.product_code,
                        "total_amount": total_amount_str,
                        "transaction_uuid": transaction_uuid,
                    },
                )

            if response.status_code != 200:
                logger.error(f"[EsewaStrategy] Status check failed for {ref_number}: {response.text}")
                return False

            data = response.json()
            return data.get("status") == "COMPLETE"

        except httpx.RequestError as e:
            logger.error(f"[EsewaStrategy] Network error verifying payment for {ref_number}: {e}")
            return False  # fail closed
        except ValueError as e:
            logger.error(f"[EsewaStrategy] Invalid JSON response verifying {ref_number}: {e}")
            return False

    async def refund(self, ref_number: str, gateway_payload: dict, amount: Decimal | None = None) -> dict:
        logger.warning(f"[EsewaStrategy] Refund requested for {ref_number} — not supported via public API")
        raise PaymentGatewayError(
            "eSewa refunds must be processed manually through the eSewa merchant portal."
        )

    async def cancel_intent(self, ref_number: str, intent_id: str) -> None:
        logger.info(f"[EsewaStrategy] No-op cancel for transaction {intent_id}")