"""Kayan voice engine — the phone channel.

A fourth process alongside backend (:8001), agent (:8002) and console
(:3000). It registers as a SIP extension, answers calls, and connects the
caller to the same Kayan agent that answers WhatsApp.

See ../SIP_INTEGRATION.md for the architecture and what came from where.
"""
