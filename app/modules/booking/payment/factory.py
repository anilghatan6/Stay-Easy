from enum import StrEnum
from app.modules.booking.payment.base_strategy import PaymentStrategy
from app.modules.booking.payment.dummy_strategy import DummyPaymentStrategy
from app.utils.exceptions import UnsupportedGatewayError
from app.utils.logging import LoggerFactory
from app.config.settings_config import settings
from app.config.redis_config import get_redis_client
logger = LoggerFactory.get_logger(__name__)


class PaymentGateway(StrEnum):
    STRIPE = "STRIPE"
    RAZORPAY = "RAZORPAY"
    DUMMY = "DUMMY"
    KHALTI = "KHALTI"
    ESEWA = "ESEWA"


class PaymentServiceFactory:
    def __init__(
        self, stripe_api_key: str, razorpay_key_id: str, razorpay_key_secret: str,
        khalti_secret_key: str,
        khalti_website_url: str,
        esewa_product_code: str,
        esewa_secret_key: str,
    ):
        self._stripe_api_key = stripe_api_key
        self._razorpay_key_id = razorpay_key_id
        self._razorpay_key_secret = razorpay_key_secret
        self._khalti_secret_key= khalti_secret_key
        self._khalti_website_url = khalti_website_url
        self._esewa_product_code = esewa_product_code
        self._esewa_secret_key = esewa_secret_key
        self._redis_client = get_redis_client()

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

        elif gateway_enum == PaymentGateway.KHALTI:
            from app.modules.booking.payment.khalti_strategy import (
                KhaltiPaymentStrategy,
            )
            return KhaltiPaymentStrategy(self._khalti_secret_key, self._khalti_website_url, self._redis_client)
        elif gateway_enum == PaymentGateway.ESEWA:
            from app.modules.booking.payment.esewa_strategy import (
                EsewaPaymentStrategy,
            )
            return EsewaPaymentStrategy(
                self._esewa_product_code, self._esewa_secret_key, self._redis_client
            )

        raise UnsupportedGatewayError(
            internal_detail=f"Unsupported payment gateway: {gateway}"
        )
