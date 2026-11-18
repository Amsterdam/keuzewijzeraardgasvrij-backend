from django.test import SimpleTestCase, override_settings


class RobotsTagMiddlewareTest(SimpleTestCase):
    @override_settings(X_ROBOTS_TAG="noindex, nofollow")
    def test_header_set_outside_production(self):
        response = self.client.get("/")
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")

    @override_settings(X_ROBOTS_TAG=None)
    def test_header_absent_in_production(self):
        response = self.client.get("/")
        self.assertNotIn("X-Robots-Tag", response.headers)
