"""Storage layer (Module 04).

Everything downstream talks to a database through :class:`DataStore`
(``store.py``) — never to SQLite or Supabase directly (CLAUDE.md hard
rule #3). ``models.py`` holds the plain dataclasses mirroring
``specs/core/schema.yaml``; ``sqlite_store.py`` and ``supabase_store.py``
are the two concrete implementations.
"""
