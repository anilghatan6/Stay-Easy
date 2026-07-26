from decimal import Decimal
from app.modules.booking.payment.factory import PaymentServiceFactory
from app.utils.exceptions import PaymentGatewayError, UnsupportedGatewayError, ServiceException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)

class PaymentService:
    def __init__(self, factory: PaymentServiceFactory):
        self.factory = factory

    async def create_intent(self, gateway: str, ref_number: str, amount: Decimal, currency: str) -> dict:
        try:
            strategy = self.factory.get_strategy(gateway)
            return await strategy.create_payment_intent(ref_number, amount, currency)
    
        except (UnsupportedGatewayError,PaymentGatewayError):
            raise
        except Exception as e:
            logger.error(f"[PaymentService] Unexpected error creating intent for {ref_number}: {e}")
            raise ServiceException("Could not initiate payment. Please try again.")

    async def verify(self, gateway: str, ref_number: str, gateway_payload: dict) -> bool:
        try:
            strategy = self.factory.get_strategy(gateway)
            return await strategy.verify_payment(ref_number, gateway_payload)
        except (UnsupportedGatewayError,PaymentGatewayError):
            raise
        except Exception as e:
            logger.error(f"[PaymentService] Unexpected error verifying payment for {ref_number}: {e}")
            return False  # fail closed — never confirm a booking on an exception

    async def refund(self, gateway: str, ref_number: str, gateway_payload: dict, amount: Decimal | None = None) -> dict:
        try:
            strategy = self.factory.get_strategy(gateway)
            logger.info(f"[PaymentService] Refund requested for {ref_number} via {gateway}")
            return await strategy.refund(ref_number, gateway_payload, amount)
        except (UnsupportedGatewayError,PaymentGatewayError):
            raise
        except Exception as e:
            logger.error(f"[PaymentService] Unexpected error refunding {ref_number}: {e}")
            raise ServiceException("Could not process refund. Please contact support.")