from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.contrib.drf import OIDCAuthentication
import requests
from django.core.exceptions import PermissionDenied
import datetime
import time


class OIDCAuthenticationBackend(OIDCAuthenticationBackend):
    def update_user(self, user, claims):
        if user.is_active is False:
            raise PermissionDenied("User account is inactive.")
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.username = claims.get("email")
        user.last_login = datetime.datetime.now(datetime.timezone.utc)
        user.save()
        return user

    def create_user(self, claims):
        user = super(OIDCAuthenticationBackend, self).create_user(claims)
        return self.update_user(user, claims)

    def validate_issuer(self, payload):
        issuer = self.get_settings("OIDC_OP_ISSUER")
        if not issuer == payload["iss"]:
            raise PermissionDenied(
                '"iss": %r does not match configured value for OIDC_OP_ISSUER: %r'
                % (payload["iss"], issuer)
            )

    def validate_audience(self, payload):
        trusted_audiences = self.get_settings("OIDC_TRUSTED_AUDIENCES", [])
        trusted_audiences = set(trusted_audiences)

        audience = payload["aud"]
        audience = set(audience)
        distrusted_audiences = audience.difference(trusted_audiences)
        if distrusted_audiences:
            raise PermissionDenied(
                '"aud" contains distrusted audiences: %r' % distrusted_audiences
            )

    def validate_expiry(self, payload):
        expire_time = payload["exp"]
        now = time.time()
        if now > expire_time:
            raise PermissionDenied(
                "Access-token is expired %r > %r" % (now, expire_time)
            )

    def validate_id_token(self, payload):
        """Validate the content of the id token as required by OpenID Connect 1.0

        This aims to fulfill point 2. 3. and 9. under section 3.1.3.7. ID Token
        Validation
        """
        self.validate_issuer(payload)
        self.validate_audience(payload)
        self.validate_expiry(payload)
        return payload

    def get_userinfo(self, access_token, id_token=None, payload=None):
        userinfo = self.verify_token(access_token)
        self.validate_id_token(userinfo)
        return userinfo

    def get_token(self, payload):
        response = requests.post(
            self.OIDC_OP_TOKEN_ENDPOINT,
            data=payload,
            verify=self.get_settings("OIDC_VERIFY_SSL", True),
            timeout=self.get_settings("OIDC_TIMEOUT", None),
            proxies=self.get_settings("OIDC_PROXY", None),
            # Add origin headers to the request because Azure requires it in the PKCE flow
            headers={"Origin": "https://test.nl"},
        )
        self.raise_token_response_error(response)
        return response.json()

    AuthenticationBackend = OIDCAuthenticationBackend
    AuthenticationClass = OIDCAuthentication
