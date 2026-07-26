
from abc import ABC, abstractmethod
from decimal import Decimal


class PaymentStrategy(ABC):
    """
    Common interface every payment gateway strategy must implement.
    PaymentService only ever talks to this interface — never to
    Stripe/Razorpay/Dummy SDKs directly.
    """

    @abstractmethod
    async def create_payment_intent(self, ref_number: str, amount: Decimal, currency: str) -> dict:
        """Create a payment intent with the given details"""
        pass
    

    @abstractmethod
    async def verify_payment(self, ref_number: str, gateway_payload: dict) -> bool:
        """Verify a payment with the given details"""
        pass

    @abstractmethod
    async def refund(self, ref_number: str, gateway_payload: dict, amount: Decimal | None = None) -> dict:
        """Refund a payment with the given details"""
        pass