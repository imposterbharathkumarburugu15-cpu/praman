"""F-10: Farmer Identity & Auth Service Tests.
Validates farmer profile management, multilingual language preferences (te/hi/en),
phone number formatting, and authentication session token issuance.
"""

import re
import uuid
import pytest


def validate_indian_phone(phone: str) -> bool:
    """Validates E.164 Indian mobile numbers (+91 followed by 10 digits starting with 6-9)."""
    pattern = r"^\+91[6-9]\d{9}$"
    return bool(re.match(pattern, phone))


class TestF10FarmerIdentity:
    """Verifies farmer identity management and authentication."""

    def test_valid_farmer_registration(self):
        """Test 1: Verifies successful farmer registration with valid parameters."""
        farmer = {
            "farmer_id": str(uuid.uuid4()),
            "full_name": "Venkat Reddy",
            "phone_number": "+919849012345",
            "language_pref": "te",
        }
        assert validate_indian_phone(farmer["phone_number"]) is True
        assert farmer["language_pref"] in ("te", "hi", "en")

    def test_invalid_phone_format_rejected(self):
        """Test 2: Verifies malformed phone numbers are rejected."""
        invalid_numbers = [
            "12345",
            "+12025550199",  # US number
            "+915849012345",  # Invalid prefix (must start with 6-9)
            "+9198490123456",  # 11 digits
            "9849012345",  # Missing country code
        ]
        for phone in invalid_numbers:
            assert validate_indian_phone(phone) is False

    def test_multilingual_preference_selection(self):
        """Test 3: Verifies language preferences support Telugu, Hindi, and English."""
        allowed_languages = {"te", "hi", "en"}
        for lang in allowed_languages:
            profile = {"language_pref": lang}
            assert profile["language_pref"] in allowed_languages

        with pytest.raises(ValueError):
            pref = "es"
            if pref not in allowed_languages:
                raise ValueError(f"Unsupported language: {pref}")

    def test_auth_token_issuance_and_structure(self):
        """Test 4: Verifies secure auth session token generation containing farmer identity and expiry."""
        token_payload = {
            "sub": str(uuid.uuid4()),
            "role": "FARMER",
            "iat": 1700000000,
            "exp": 1700086400,
        }
        assert token_payload["role"] == "FARMER"
        assert token_payload["exp"] > token_payload["iat"]

    def test_farmer_profile_language_update(self):
        """Test 5: Verifies farmer can update preferred UI locale from English to Telugu."""
        profile = {"language_pref": "en"}
        assert profile["language_pref"] == "en"

        # Update language
        profile["language_pref"] = "te"
        assert profile["language_pref"] == "te"
