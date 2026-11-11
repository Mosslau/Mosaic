import unittest

from mosaic_ai_contracts.contracts import CONTRACTS, EXAMPLES


class AIContractsTest(unittest.TestCase):
    def test_every_example_passes(self):
        for name, payload in EXAMPLES.items():
            with self.subTest(contract=name):
                self.assertEqual([], CONTRACTS.validate(name, payload))

    def test_missing_required_field(self):
        payload = dict(EXAMPLES["Service"])
        payload.pop("endpoint")
        errors = CONTRACTS.validate("Service", payload)
        self.assertTrue(any("missing required field: endpoint" in e for e in errors))

    def test_enum_is_enforced(self):
        payload = dict(EXAMPLES["AssetRef"], kind="weights")
        errors = CONTRACTS.validate("AssetRef", payload)
        self.assertTrue(any("not in" in e for e in errors))

    def test_answer_citations_must_be_array_of_objects(self):
        payload = dict(EXAMPLES["Answer"], citations=["not-an-object"])
        errors = CONTRACTS.validate("Answer", payload)
        self.assertTrue(any("citations[0]" in e for e in errors))

    def test_confidence_must_be_number(self):
        payload = dict(EXAMPLES["Answer"], confidence="high")
        errors = CONTRACTS.validate("Answer", payload)
        self.assertTrue(any("confidence" in e for e in errors))

    def test_runtime_capabilities_are_strings(self):
        payload = dict(EXAMPLES["RuntimePort"], capabilities=["publish", 1])
        errors = CONTRACTS.validate("RuntimePort", payload)
        self.assertTrue(any("capabilities[1]" in e for e in errors))

    def test_unknown_contract(self):
        self.assertEqual(["unknown contract: Nope"], CONTRACTS.validate("Nope", {}))

    def test_schema_shape(self):
        schema = CONTRACTS.schema("RuntimePort")
        self.assertEqual("RuntimePort", schema["title"])
        self.assertIn("runtime_id", schema["required"])
        self.assertEqual(5, len(CONTRACTS.names()))


if __name__ == "__main__":
    unittest.main()
