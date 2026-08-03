import uuid
from decimal import Decimal
from app.modules.booking.payment.base_strategy import PaymentStrategy
from app.utils.logging import LoggerFactory
from typing import Optional
logger = LoggerFactory.get_logger(__name__)


class DummyPaymentStrategy(PaymentStrategy):
    """Simulates a gateway locally — always succeeds. No network calls."""

    async def create_payment_intent(self, ref_number: str, amount: Decimal, currency: str,return_url: Optional[str] = None) -> dict:
        logger.info(f"[DummyStrategy] Creating fake payment intent for {ref_number}")
        return {
            "payment_intent_id": f"dummy_pi_{uuid.uuid4().hex[:12]}",
            "client_secret": f"dummy_secret_{uuid.uuid4().hex[:12]}",
        }

    async def verify_payment(self, ref_number: str, gateway_payload: dict) -> bool:
        logger.info(f"[DummyStrategy] Auto-verifying payment for {ref_number}")
        return True

    async def refund(self, ref_number: str, gateway_payload: dict, amount: Decimal | None = None) -> dict:
        logger.info(f"[DummyStrategy] Simulating refund for {ref_number}")
        return {"refund_id": f"dummy_refund_{uuid.uuid4().hex[:12]}", "status": "succeeded"}