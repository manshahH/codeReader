"""A2 email capture (docs/10; D-120).

Scope is deliberately narrow: capture an address, prove the user controls it,
and let them withdraw it. Reminders and the weekly recap are A3 and live
nowhere in this package yet -- what A3 inherits from here is the sender seam
and the guarantee that `users.email` is either deliverable or NULL.
"""
