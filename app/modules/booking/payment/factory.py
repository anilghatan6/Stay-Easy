from enum import StrEnum
from app.modules.booking.payment.base_strategy import PaymentStrategy
from app.modules.booking.payment.dummy_strategy import DummyPaymentStrategy
from app.utils.exceptions import UnsupportedGatewayError
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class PaymentGateway(StrEnum):
    STRIPE = "STRIPE"
    RAZORPAY = "RAZORPAY"
    DUMMY = "DUMMY"


class PaymentServiceFactory:
    def __init__(
        self, stripe_api_key: str, razorpay_key_id: str, razorpay_key_secret: str
    ):
        self._stripe_api_key = stripe_api_key
        self._razorpay_key_id = razorpay_key_id
        self._razorpay_key_secret = razorpay_key_secret

    def get_strategy(self, gateway: str) -> PaymentStrategy:
        try:
            gateway_enum = PaymentGateway(gateway.upper())
        except ValueError as e:
            logger.error(f"[PaymentFactory] Unknown gateway requested: {gateway}")
            raise UnsupportedGatewayError(
                internal_detail=f"Unsupported payment gateway: {gateway}"
            ) from e

        if gateway_enum == PaymentGateway.STRIPE:
            from app.modules.booking.payment.stripe_strategy import (
                StripePaymentStrategy,
            )

            return StripePaymentStrategy(self._stripe_api_key)
        elif gateway_enum == PaymentGateway.RAZORPAY:
            from app.modules.booking.payment.razorpay_strategy import (
                RazorpayPaymentStrategy,
            )

            return RazorpayPaymentStrategy(
                self._razorpay_key_id, self._razorpay_key_secret
            )
        elif gateway_enum == PaymentGateway.DUMMY:
            return DummyPaymentStrategy()

        raise UnsupportedGatewayError(
            internal_detail=f"Unsupported payment gateway: {gateway}"
        )
