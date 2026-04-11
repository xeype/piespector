from __future__ import annotations

import unittest

from piespector.auth_provider import build_auth_provider
from piespector.domain.requests import RequestDefinition
from piespector.secrets import (
    auth_preview_header_display_overrides,
    is_sensitive_header_name,
    mask_auth_header_display,
    mask_header_display,
    mask_secret_display,
)


class SecretDisplayTests(unittest.TestCase):
    def test_mask_secret_display_preserves_last_four_characters(self) -> None:
        self.assertEqual(mask_secret_display("secret-token"), "********oken")

    def test_mask_secret_display_leaves_placeholder_reference_visible(self) -> None:
        self.assertEqual(mask_secret_display("{{API_KEY}}"), "{{API_KEY}}")

    def test_mask_auth_header_display_preserves_authorization_prefix(self) -> None:
        masked = mask_auth_header_display("Authorization", "Bearer secret-token")

        self.assertEqual(masked, "Bearer ********oken")

    def test_mask_auth_header_display_leaves_authorization_placeholder_visible(self) -> None:
        masked = mask_auth_header_display("Authorization", "Bearer {{API_KEY}}")

        self.assertEqual(masked, "Bearer {{API_KEY}}")

    def test_mask_auth_header_display_preserves_cookie_name(self) -> None:
        masked = mask_auth_header_display("Cookie", "session=secret-token")

        self.assertEqual(masked, "session=********oken")

    def test_mask_header_display_masks_sensitive_explicit_header_values(self) -> None:
        masked = mask_header_display("X-API-Key", "secret-token")

        self.assertEqual(masked, "********oken")

    def test_mask_header_display_leaves_sensitive_placeholder_header_values_visible(self) -> None:
        masked = mask_header_display("X-API-Key", "{{API_KEY}}")

        self.assertEqual(masked, "{{API_KEY}}")

    def test_mask_header_display_leaves_non_sensitive_headers_visible(self) -> None:
        self.assertEqual(mask_header_display("Accept", "application/json"), "application/json")

    def test_sensitive_header_name_matches_auth_headers(self) -> None:
        self.assertTrue(is_sensitive_header_name("Authorization"))
        self.assertTrue(is_sensitive_header_name("X-API-Key"))
        self.assertFalse(is_sensitive_header_name("Accept"))

    def test_api_key_auth_preview_can_be_masked_for_header_table(self) -> None:
        request = RequestDefinition(
            auth_type="api-key",
            auth_api_key_name="X-API-Key",
            auth_api_key_value="secret-token",
            auth_api_key_location="header",
        )

        preview_headers = dict(build_auth_provider(request, {}).preview_header_items())
        masked = {
            key: mask_auth_header_display(key, value)
            for key, value in preview_headers.items()
        }

        self.assertEqual(masked["X-API-Key"], "********oken")

    def test_auth_preview_override_keeps_api_key_placeholder_visible(self) -> None:
        request = RequestDefinition(
            auth_type="api-key",
            auth_api_key_name="X-API-Key",
            auth_api_key_value="{{API_KEY}}",
            auth_api_key_location="header",
        )

        overrides = auth_preview_header_display_overrides(
            request,
            {"API_KEY": "secret-token"},
        )

        self.assertEqual(overrides["x-api-key"], "{{API_KEY}}")

    def test_auth_preview_override_keeps_bearer_placeholder_visible(self) -> None:
        request = RequestDefinition(
            auth_type="bearer",
            auth_bearer_prefix="Bearer",
            auth_bearer_token="{{API_KEY}}",
        )

        overrides = auth_preview_header_display_overrides(
            request,
            {"API_KEY": "secret-token"},
        )

        self.assertEqual(overrides["authorization"], "Bearer {{API_KEY}}")


if __name__ == "__main__":
    unittest.main()
