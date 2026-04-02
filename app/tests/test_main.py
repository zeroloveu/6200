import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.chain_service import ChainServiceError, _run_bridge_command
from app.main import (
    is_live_poll_available_to_user,
    is_poll_mutable,
    now_utc,
    poll_status_from_model,
    verify_chain_sync_payload,
)
from app.models import Poll, User


class PollMutationRulesTests(unittest.TestCase):
    def test_pending_poll_without_votes_is_mutable(self) -> None:
        poll = Poll(
            topic="Budget Vote",
            starts_at=now_utc() + timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=2),
            options_json='["Yes","No"]',
            allowed_user_ids_json="[1]",
            created_by_user_id=1,
        )

        self.assertEqual(poll_status_from_model(poll), "pending")
        self.assertTrue(is_poll_mutable(poll))

    def test_active_poll_without_synced_votes_is_not_mutable(self) -> None:
        poll = Poll(
            topic="Budget Vote",
            starts_at=now_utc() - timedelta(minutes=5),
            ends_at=now_utc() + timedelta(hours=1),
            options_json='["Yes","No"]',
            allowed_user_ids_json="[1]",
            created_by_user_id=1,
        )

        self.assertEqual(poll_status_from_model(poll), "active")
        self.assertFalse(is_poll_mutable(poll))

    def test_ended_poll_is_not_available_in_live_lists_even_if_user_is_allowed(self) -> None:
        user = User(id=1, username="alice", password_hash="hashed", wallet_address="0x2222222222222222222222222222222222222222")
        poll = Poll(
            topic="Budget Vote",
            starts_at=now_utc() - timedelta(hours=2),
            ends_at=now_utc() - timedelta(minutes=1),
            options_json='["Yes","No"]',
            allowed_user_ids_json="[1]",
            created_by_user_id=2,
        )

        self.assertEqual(poll_status_from_model(poll), "ended")
        self.assertFalse(is_live_poll_available_to_user(poll, user))


class ChainSyncVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.poll = Poll(
            topic="Council Election",
            starts_at=now_utc() - timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=1),
            options_json='["Alice","Bob"]',
            allowed_user_ids_json="[1]",
            created_by_user_id=1,
            chain_contract_address="0x1111111111111111111111111111111111111111",
            chain_deploy_block=123,
        )
        self.user = User(
            username="alice",
            password_hash="hashed",
            wallet_address="0x2222222222222222222222222222222222222222",
        )
        self.vote_tx_hash = f"0x{'a' * 64}"

    @patch("app.main.fetch_voter_action")
    def test_verify_chain_sync_payload_uses_chain_data_as_source_of_truth(self, fetch_voter_action_mock) -> None:
        fetch_voter_action_mock.return_value = {
            "actionType": "vote",
            "candidateId": 1,
            "txHash": f"0x{'A' * 64}",
        }

        result = verify_chain_sync_payload(
            poll=self.poll,
            user=self.user,
            action_type="vote",
            tx_hash=self.vote_tx_hash,
            candidate_id="1",
        )

        self.assertEqual(
            result,
            {
                "action_type": "vote",
                "candidate_id": 1,
                "tx_hash": f"0x{'A' * 64}",
            },
        )
        fetch_voter_action_mock.assert_called_once_with(
            contract_address=self.poll.chain_contract_address,
            voter_address=self.user.wallet_address,
            from_block=self.poll.chain_deploy_block,
        )

    @patch("app.main.fetch_voter_action")
    def test_verify_chain_sync_payload_rejects_mismatched_candidate(self, fetch_voter_action_mock) -> None:
        fetch_voter_action_mock.return_value = {
            "actionType": "vote",
            "candidateId": 0,
            "txHash": self.vote_tx_hash,
        }

        with self.assertRaisesRegex(ValueError, "候选项编号与链上记录不一致"):
            verify_chain_sync_payload(
                poll=self.poll,
                user=self.user,
                action_type="vote",
                tx_hash=self.vote_tx_hash,
                candidate_id="1",
            )

    @patch("app.main.fetch_voter_action")
    def test_verify_chain_sync_payload_rejects_missing_wallet(self, fetch_voter_action_mock) -> None:
        walletless_user = User(username="alice", password_hash="hashed", wallet_address=None)

        with self.assertRaisesRegex(ValueError, "绑定钱包地址"):
            verify_chain_sync_payload(
                poll=self.poll,
                user=walletless_user,
                action_type="vote",
                tx_hash=self.vote_tx_hash,
                candidate_id="1",
            )

        fetch_voter_action_mock.assert_not_called()


class ChainBridgeTests(unittest.TestCase):
    @patch("app.chain_service.subprocess.run")
    def test_run_bridge_command_parses_json_output(self, subprocess_run_mock) -> None:
        subprocess_run_mock.return_value = SimpleNamespace(
            returncode=0,
            stdout='{"status":"ok","title":"中文投票"}',
            stderr="",
        )

        result = _run_bridge_command("summary", {"contractAddress": "0x1111111111111111111111111111111111111111"})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["title"], "中文投票")

    @patch("app.chain_service.subprocess.run")
    def test_run_bridge_command_rejects_empty_stdout(self, subprocess_run_mock) -> None:
        subprocess_run_mock.return_value = SimpleNamespace(
            returncode=0,
            stdout=None,
            stderr="",
        )

        with self.assertRaisesRegex(ChainServiceError, "没有返回可解析的数据"):
            _run_bridge_command("summary", {"contractAddress": "0x1111111111111111111111111111111111111111"})


if __name__ == "__main__":
    unittest.main()
