"""Module 19 — real login/session auth (multi-tenant v2).

``password.py`` hashes/verifies via bcrypt (an established KDF, not a
hand-rolled hash). ``validation.py`` is registration input validation
(email shape, password strength). Neither module touches Flask or the
DataStore — pure functions, easy to unit test in isolation.
"""
