import razorpay
from decimal import Decimal
from app.modules.booking.payment.base_strategy import PaymentStrategy
from app.utils.exceptions import PaymentGatewayError
from app.utils.logging import LoggerFactory
from dotenv import load_dotenv

load_dotenv()
logger = LoggerFactory.get_logger(__name__)


class RazorpayPaymentStrategy(PaymentStrategy):
    def __init__(self, key_id: str, key_secret: str):
        self.client = razorpay.Client(auth=(key_id, key_secret))

    async def create_payment_intent(
        self, ref_number: str, amount: Decimal, currency: str
    ) -> dict:
        logger.info(f"[RazorpayStrategy] Creating order for {ref_number}")
        try:
            order = self.client.order.create(
                {
                    "amount": int(amount * 100),
                    "currency": currency.upper(),
                    "receipt": ref_number,
                }
            )
            return {"order_id": order["id"]}
        except razorpay.errors.BadRequestError as e:
            logger.error(
                f"[RazorpayStrategy] Failed to create order for {ref_number}: {e}"
            )
            raise PaymentGatewayError(
                internal_detail=f"Razorpay error: {str(e)}"
            ) from e

    async def verify_payment(self, ref_number: str, gateway_payload: dict) -> bool:
        order_id = gateway_payload.get("razorpay_order_id") or gateway_payload.get("order_id")
        payment_id = gateway_payload.get("razorpay_payment_id") or gateway_payload.get("payment_id")
        signature = gateway_payload.get("razorpay_signature") or gateway_payload.get("signature")

        if not all([order_id, payment_id, signature]):
            logger.error(
                f"[RazorpayStrategy] Missing verification fields for {ref_number}"
            )
            return False

        try:
            self.client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                }
            )
            return True
        except razorpay.errors.SignatureVerificationError:
            logger.error(
                f"[RazorpayStrategy] Signature verification failed for {ref_number}"
            )
            return False

    async def refund(
        self, ref_number: str, gateway_payload: dict, amount: Decimal | None = None
    ) -> dict:
        logger.info(f"[RazorpayStrategy] Refunding {ref_number}")
        payment_id = gateway_payload.get("razorpay_payment_id") or gateway_payload.get("payment_id")
        if not payment_id:
            raise PaymentGatewayError(
                internal_detail="Missing payment_id — cannot process refund"
            )

        try:
            kwargs = {}
            if amount is not None:
                kwargs["amount"] = int(amount * 100)
            refund = self.client.payment.refund(payment_id, kwargs)
            return {"refund_id": refund["id"], "status": refund["status"]}
        except razorpay.errors.BadRequestError as e:
            logger.error(f"[RazorpayStrategy] Failed to refund {ref_number}: {e}")
            raise PaymentGatewayError(
                internal_detail=f"Razorpay refund error: {str(e)}"
            ) from e
