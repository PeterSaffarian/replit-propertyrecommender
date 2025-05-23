#!/usr/bin/env python3
"""
property_recommender/data_gathering/providers/trademe_token_gen.py

Script to generate and store OAuth access tokens for the Trade Me API.

This will:
  1. Read your CONSUMER_KEY and CONSUMER_SECRET from .env.
  2. Fetch a temporary request token from the sandbox.
  3. Show you the authorize URL—visit it and approve the app.
  4. Prompt you for the PIN (verifier) returned on approval.
  5. Exchange the verifier for a long-lived access token & secret.
  6. Write TRADEME_OAUTH_TOKEN and TRADEME_OAUTH_TOKEN_SECRET into your .env.

Usage:
    cd property_recommender
    python data_gathering/providers/trademe_token_gen.py
"""

import os
import sys
from urllib.parse import parse_qs
from requests_oauthlib import OAuth1Session
from dotenv import load_dotenv, find_dotenv, set_key

# OAuth endpoints for the sandbox
REQUEST_TOKEN_URL    = "https://api.tmsandbox.co.nz/Oauth/RequestToken?scope=MyTradeMeRead"
AUTHORIZE_URL        = "https://www.tmsandbox.co.nz/Oauth/Authorize"
ACCESS_TOKEN_URL     = "https://api.tmsandbox.co.nz/Oauth/AccessToken"

def main():
    # 1. Load .env
    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path:
        print("❌ Could not find a .env file. Create one from .env.example first.")
        sys.exit(1)
    load_dotenv(dotenv_path)

    # 2. Read consumer credentials
    consumer_key    = os.getenv("TRADEME_CONSUMER_KEY")
    consumer_secret = os.getenv("TRADEME_CONSUMER_SECRET")
    if not consumer_key or not consumer_secret:
        print("❌ TRADEME_CONSUMER_KEY and/or TRADEME_CONSUMER_SECRET not set in .env")
        sys.exit(1)

    # 3. Obtain a request token (PIN-based)
    print("🔑 Fetching request token from Trade Me sandbox...")
    oauth = OAuth1Session(
        client_key=consumer_key,
        client_secret=consumer_secret,
        callback_uri="oob"       # out-of-band (PIN-based) flow
    )
    fetch_resp = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    resource_owner_key    = fetch_resp.get("oauth_token")
    resource_owner_secret = fetch_resp.get("oauth_token_secret")
    if not resource_owner_key or not resource_owner_secret:
        print("❌ Failed to obtain request token.")
        sys.exit(1)

    # 4. Direct user to authorize URL
    auth_url = oauth.authorization_url(AUTHORIZE_URL)
    print("\nPlease visit this URL in your browser to authorize the app:\n")
    print(f"  {auth_url}\n")
    print("After approval, you will be shown a PIN (verifier).")
    verifier = input("Enter the PIN here: ").strip()
    if not verifier:
        print("❌ No PIN entered; exiting.")
        sys.exit(1)

    # 5. Exchange for access token
    oauth = OAuth1Session(
        client_key=consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=verifier
    )
    access_resp = oauth.fetch_access_token(ACCESS_TOKEN_URL)
    access_token        = access_resp.get("oauth_token")
    access_token_secret = access_resp.get("oauth_token_secret")
    if not access_token or not access_token_secret:
        print("❌ Failed to obtain access token.")
        sys.exit(1)

    # 6. Persist to .env
    print("\n✅ Successfully obtained OAuth tokens. Writing to .env…")
    set_key(dotenv_path, "TRADEME_OAUTH_TOKEN", access_token)
    set_key(dotenv_path, "TRADEME_OAUTH_TOKEN_SECRET", access_token_secret)
    print("✅ .env updated with TRADEME_OAUTH_TOKEN and TRADEME_OAUTH_TOKEN_SECRET")
    print("You can now re-run your pipeline against the sandbox.")

if __name__ == "__main__":
    main()
