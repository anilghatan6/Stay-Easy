import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from app.modules.booking.payment.khalti_strategy import KhaltiPaymentStrategy
from app.utils.exceptions import PaymentGatewayError


@pytest.mark.asyncio
async def test_khalti_init_missing_secret_key():
    with pytest.raises(PaymentGatewayError) as exc:
        KhaltiPaymentStrategy(secret_key="", website_url="https://example.com")
    assert "Khalti secret key is not configured" in str(exc.value)


@pytest.mark.asyncio
async def test_khalti_create_payment_intent_invalid_currency():
    strategy = KhaltiPaymentStrategy(secret_key="test_secret", website_url="https://example.com")
    with pytest.raises(PaymentGatewayError) as exc:
        await strategy.create_payment_intent(
            ref_number="BK-1234",
            amount=Decimal("100.00"),
            currency="USD",
            return_url="https://example.com/return"
        )
    assert "Khalti only supports NPR" in str(exc.value)


@pytest.mark.asyncio
async def test_khalti_create_payment_intent_success():
    strategy = KhaltiPaymentStrategy(secret_key="test_secret", website_url="https://example.com")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "pidx": "test_pidx_123",
        "payment_url": "https://khalti.com/pay/test_pidx_123"
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        res = await strategy.create_payment_intent(
            ref_number="BK-1234",
            amount=Decimal("1500.50"),
            currency="NPR",
            return_url="https://example.com/return"
        )

        assert res["payment_intent_id"] == "test_pidx_123"
        assert res["payment_url"] == "https://khalti.com/pay/test_pidx_123"

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["amount"] == 150050  # 1500.50 NPR = 150050 Paisa
        assert call_kwargs["json"]["purchase_order_id"] == "BK-1234"
        assert call_kwargs["json"]["return_url"] == "https://example.com/return"


@pytest.mark.asyncio
async def test_khalti_verify_payment_success():
    strategy = KhaltiPaymentStrategy(secret_key="test_secret", website_url="https://example.com")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "pidx": "test_pidx_123",
        "status": "Completed",
        "total_amount": 150050
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        is_valid = await strategy.verify_payment(
            ref_number="BK-1234",
            gateway_payload={"pidx": "test_pidx_123"}
        )
        assert is_valid is True


@pytest.mark.asyncio
async def test_khalti_verify_payment_not_completed():
    strategy = KhaltiPaymentStrategy(secret_key="test_secret", website_url="https://example.com")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "pidx": "test_pidx_123",
        "status": "Pending",
        "total_amount": 150050
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        is_valid = await strategy.verify_payment(
            ref_number="BK-1234",
            gateway_payload={"pidx": "test_pidx_123"}
        )
        assert is_valid is False


@pytest.mark.asyncio
async def test_khalti_verify_payment_missing_pidx():
    strategy = KhaltiPaymentStrategy(secret_key="test_secret", website_url="https://example.com")
    is_valid = await strategy.verify_payment(ref_number="BK-1234", gateway_payload={})
    assert is_valid is False


@pytest.mark.asyncio
async def test_khalti_refund_unsupported():
    strategy = KhaltiPaymentStrategy(secret_key="test_secret", website_url="https://example.com")
    with pytest.raises(PaymentGatewayError) as exc:
        await strategy.refund(ref_number="BK-1234", gateway_payload={"pidx": "test_pidx_123"})
    assert "Khalti refunds must be processed manually" in str(exc.value)
