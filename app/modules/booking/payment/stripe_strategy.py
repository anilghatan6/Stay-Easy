import stripe
from decimal import Decimal
from app.modules.booking.payment.base_strategy import PaymentStrategy
from app.utils.exceptions import PaymentGatewayError
from app.utils.logging import LoggerFactory
from typing import Optional

logger = LoggerFactory.get_logger(__name__)

class StripePaymentStrategy(PaymentStrategy):
    def __init__(self, api_key: str):
        self._client_configured = bool(api_key)
        logger.info(f"[StripeStrategy] Client configured: {self._client_configured}")
        # logger.info(f"[StripeStrategy] API key: {api_key}")
        stripe.api_key = api_key

    async def create_payment_intent(self, ref_number: str, amount: Decimal, currency: str,return_url: Optional[str] = None) -> dict:
        logger.info(f"[StripeStrategy] Creating payment intent for {ref_number}")
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency=currency.lower(),
                metadata={"ref_number": ref_number},
            )
            return {"client_secret": intent.client_secret, "payment_intent_id": intent.id}
        except stripe.error.StripeError as e:
            logger.error(f"[StripeStrategy] Failed to create payment intent for {ref_number}: {e}")
            raise PaymentGatewayError(internal_detail=f"Stripe error: {str(e)}") from e

    async def verify_payment(self, ref_number: str, gateway_payload: dict) -> bool:
        payment_intent_id = gateway_payload.get("payment_intent_id")
        if not payment_intent_id:
            logger.error(f"[StripeStrategy] Missing payment_intent_id for {ref_number}")
            return False
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return intent.status == "succeeded"
        except stripe.error.StripeError as e:
            logger.error(f"[StripeStrategy] Failed to verify payment for {ref_number}: {e}")
            return False

    async def refund(self, ref_number: str, gateway_payload: dict, amount: Decimal | None = None) -> dict:
        logger.info(f"[StripeStrategy] Refunding {ref_number}")
        payment_intent_id = gateway_payload.get("payment_intent_id")
        if not payment_intent_id:
            raise PaymentGatewayError(internal_detail="Missing payment_intent_id — cannot process refund")
        try:
            kwargs = {"payment_intent": payment_intent_id}
            if amount is not None:
                kwargs["amount"] = int(amount * 100)
            refund = stripe.Refund.create(**kwargs)
            return {"refund_id": refund.id, "status": refund.status}
        except stripe.error.StripeError as e:
            logger.error(f"[StripeStrategy] Failed to refund {ref_number}: {e}")
            raise PaymentGatewayError(internal_detail=f"Stripe refund error: {str(e)}") from e