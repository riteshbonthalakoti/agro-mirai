"""Email OTP for the admin "forgot password" flow.

Uses Supabase Auth's own built-in email delivery (``auth.sign_in_with_otp`` /
``auth.verify_otp``) rather than standing up a separate email-sending
service -- Supabase's free tier sends these for you. This is deliberately
decoupled from the ``farmers`` table (our own user records): Supabase Auth
here is used purely as an email-ownership verifier, never as the source of
truth for who's an admin. A verified OTP only unlocks resetting the
password on the matching ``farmers`` row.
"""
import os


def _auth_client():
    from supabase import create_client  # local import: optional dep

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def send_reset_otp(email: str) -> bool:
    """Sends a one-time passcode to `email` via Supabase Auth. Returns
    False (never raises) if Supabase isn't configured or the send fails --
    the caller always shows the same "if that email has admin access, a
    code was sent" message either way, so this never confirms or denies
    whether an address has admin access."""
    client = _auth_client()
    if client is None:
        return False
    try:
        client.auth.sign_in_with_otp({"email": email, "options": {"should_create_user": False}})
        return True
    except Exception:
        return False


def verify_reset_otp(email: str, code: str) -> bool:
    """True iff `code` is a valid, unexpired OTP for `email`."""
    client = _auth_client()
    if client is None:
        return False
    try:
        client.auth.verify_otp({"email": email, "token": code, "type": "email"})
        return True
    except Exception:
        return False
