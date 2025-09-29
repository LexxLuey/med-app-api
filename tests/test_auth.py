"""Unit tests for authentication module."""


class TestAuthFunctions:
    """Test authentication utility functions."""

    def test_authenticate_user_success(self):
        """Test successful user authentication."""
        from auth.router import authenticate_user

        user = authenticate_user("admin", "pass")
        assert user is not None
        assert isinstance(user, dict)
        assert user["username"] == "admin"

    def test_authenticate_user_failure(self):
        """Test failed user authentication."""
        from auth.router import authenticate_user

        user = authenticate_user("admin", "wrong_password")
        assert user is False


class TestJWT:
    """Test JWT token operations."""

    def test_create_access_token(self):
        """Test JWT token creation."""
        from auth.router import create_access_token

        data = {"sub": "testuser"}
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 100  # JWT tokens are reasonably long
