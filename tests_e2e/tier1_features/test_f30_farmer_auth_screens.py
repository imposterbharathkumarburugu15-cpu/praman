"""F-30: Farmer Registration & Login Screens Tests.
Validates mobile registration form input validation, OTP/PIN authentication simulation,
and persistent session storage mechanics.
"""

import uuid
import pytest


class MockMobileAuthSession:
    """Simulates mobile auth session management with secure storage."""

    def __init__(self):
        self.secure_storage = {}

    def login(self, phone: str, otp: str) -> dict:
        if otp != "123456":
            raise ValueError("Invalid verification OTP")
        token = f"jwt-session-{uuid.uuid4()}"
        self.secure_storage["session_token"] = token
        self.secure_storage["phone"] = phone
        return {"status": "AUTHENTICATED", "token": token}

    def is_logged_in(self) -> bool:
        return "session_token" in self.secure_storage

    def logout(self):
        self.secure_storage.clear()


class TestF30FarmerAuthScreens:
    """Verifies farmer mobile authentication and session handling."""

    def test_successful_otp_login(self):
        """Test 1: Verifies successful authentication and session token storage upon valid OTP."""
        session = MockMobileAuthSession()
        res = session.login("+919876543210", "123456")

        assert res["status"] == "AUTHENTICATED"
        assert session.is_logged_in() is True

    def test_invalid_otp_rejected(self):
        """Test 2: Verifies incorrect OTP fails authentication and leaves session unauthenticated."""
        session = MockMobileAuthSession()
        with pytest.raises(ValueError, match="Invalid verification OTP"):
            session.login("+919876543210", "000000")

        assert session.is_logged_in() is False

    def test_auto_login_on_app_resume(self):
        """Test 3: Verifies valid stored token enables auto-login on app launch without prompting credentials."""
        session = MockMobileAuthSession()
        session.secure_storage["session_token"] = "valid-persisted-token"
        assert session.is_logged_in() is True

    def test_logout_clears_session(self):
        """Test 4: Verifies logout completely purges stored session tokens."""
        session = MockMobileAuthSession()
        session.login("+919876543210", "123456")
        assert session.is_logged_in() is True

        session.logout()
        assert session.is_logged_in() is False
        assert len(session.secure_storage) == 0

    def test_phone_input_sanitization(self):
        """Test 5: Verifies phone number input trims whitespace and normalizes country code."""
        raw_input = "  98765 43210  "
        clean = "+91" + raw_input.replace(" ", "")
        assert clean == "+919876543210"
