"""
Minimal Google OAuth2 helper.
No extra library required — uses only the `requests` package
which is already a transitive dependency.
"""
import secrets
import urllib.parse

import requests
from django.conf import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def generate_state():
    return secrets.token_hex(32)


def get_authorization_url(redirect_uri, state):
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_user_info(code, redirect_uri):
    """
    Exchange the authorization code for an access token, then fetch
    the user's profile from Google's userinfo endpoint.

    Returns a dict with at least: email, name, verified_email
    Raises ValueError if anything goes wrong.
    """
    token_response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )

    if not token_response.ok:
        raise ValueError(
            f"Token exchange failed: {token_response.status_code} "
            f"{token_response.text}"
        )

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("No access_token in Google token response.")

    userinfo_response = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )

    if not userinfo_response.ok:
        raise ValueError(
            f"Userinfo fetch failed: {userinfo_response.status_code} "
            f"{userinfo_response.text}"
        )

    return userinfo_response.json()
