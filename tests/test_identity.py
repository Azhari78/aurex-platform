"""Unit tests for Identity, Out-of-Band confirmation, and anti-replay."""

import unittest
from aurex.core.identity import (
    IdentityManager,
    InvalidSignatureError,
    ReplayConfirmationError,
)
from aurex.core.models import UserConfirmation


class TestIdentityManager(unittest.TestCase):
    def setUp(self):
        self.identity = IdentityManager()
        self.identity.register_user("officer1", "RISK_ADMIN", "secret_key_1234567890abcdef", "Risk Officer")

    def test_generate_and_verify_confirmation(self):
        conf = self.identity.generate_confirmation(
            user_id="officer1",
            request_id="req_999",
            proposal_digest="digest_abc123"
        )
        self.assertTrue(self.identity.verify_confirmation(conf))

    def test_replay_confirmation_rejected(self):
        conf = self.identity.generate_confirmation(
            user_id="officer1",
            request_id="req_999",
            proposal_digest="digest_abc123"
        )
        self.identity.verify_confirmation(conf)
        # Attempting second time must raise ReplayConfirmationError
        with self.assertRaises(ReplayConfirmationError):
            self.identity.verify_confirmation(conf)

    def test_tampered_signature_rejected(self):
        conf = self.identity.generate_confirmation(
            user_id="officer1",
            request_id="req_999",
            proposal_digest="digest_abc123"
        )
        # Tamper signature
        bad_conf = UserConfirmation(
            confirmation_id=conf.confirmation_id,
            request_id=conf.request_id,
            proposal_digest=conf.proposal_digest,
            user_id=conf.user_id,
            channel=conf.channel,
            confirmed_at_utc=conf.confirmed_at_utc,
            signature="tampered_signature_hex"
        )
        with self.assertRaises(InvalidSignatureError):
            self.identity.verify_confirmation(bad_conf)


if __name__ == "__main__":
    unittest.main()
