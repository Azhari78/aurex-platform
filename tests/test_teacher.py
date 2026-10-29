"""Unit tests for AIA Teacher controlled learning pipeline and provenance."""

import unittest
from aurex.teacher.provenance import ProvenanceRegistry
from aurex.teacher.supervisor import AIATeacherSupervisor


class TestAIATeacher(unittest.TestCase):
    def setUp(self):
        self.provenance = ProvenanceRegistry()
        self.teacher = AIATeacherSupervisor(self.provenance)

    def test_complete_learning_pipeline(self):
        # 1. Observe
        trades = [{"profit": 10.0, "slippage": 1.0}, {"profit": -5.0, "slippage": 1.5}]
        obs = self.teacher.observe_performance("ENGINE_CRYPTO", trades)
        self.assertEqual(obs["total_trades"], 2)

        # 2. Diagnose
        diag = self.teacher.diagnose_weakness(obs)
        self.assertIn("diagnosis_id", diag)

        # 3. Hypothesis & Provenance
        record = self.teacher.formulate_hypothesis(
            diagnosis=diag,
            hypothesis_statement="Dynamic volatility band adjustment",
            affected_module="aurex.engines.crypto"
        )
        self.assertEqual(record.validation_status, "PENDING")
        self.assertTrue(len(record.provenance_hash) == 64)

        # 4. Sandbox Validation
        validated = self.teacher.run_sandbox_validation(record.hypothesis_id)
        self.assertEqual(validated.validation_status, "PASS")

        # 5. Approval Gate
        approved = self.provenance.approve_experiment(record.hypothesis_id, "admin_user")
        self.assertEqual(approved.approved_by, "admin_user")
        self.assertIsNotNone(approved.approval_timestamp_utc)


if __name__ == "__main__":
    unittest.main()
