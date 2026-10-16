from django.core.cache import cache
from django.test import TestCase


class SecurityHeadersTest(TestCase):
    def setUp(self):
        # Reset the anonymous API throttle shared with other tests.
        cache.clear()

    def test_hsts_header_on_https_behind_gateway(self):
        response = self.client.get("/", headers={"X-Forwarded-Proto": "https"})

        self.assertEqual(
            response.headers["Strict-Transport-Security"], "max-age=31536000"
        )

    def test_no_hsts_header_on_plain_http(self):
        response = self.client.get("/")

        self.assertNotIn("Strict-Transport-Security", response.headers)

    def test_csp_header(self):
        response = self.client.get("/")

        csp = response.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertNotIn("cdn.jsdelivr.net", csp)

    def test_swagger_ui_csp_allows_cdn(self):
        response = self.client.get("/api/schema/swagger/")

        self.assertEqual(response.status_code, 200)
        csp = response.headers["Content-Security-Policy"]
        self.assertIn("script-src 'self' https://cdn.jsdelivr.net", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        # The split view serves its init script separately, so no inline script.
        self.assertNotIn(b"<script>", response.content)

    def test_api_responses_are_not_cached(self):
        response = self.client.get("/api/schema/")

        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_non_api_responses_keep_default_caching(self):
        response = self.client.get("/")

        self.assertNotIn("Cache-Control", response.headers)
