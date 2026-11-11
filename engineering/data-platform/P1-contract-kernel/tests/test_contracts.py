import unittest

from mosaic_data_contracts.contracts import CONTRACTS, EXAMPLES


class DataContractsTest(unittest.TestCase):
    def test_every_example_passes(self):
        for name, payload in EXAMPLES.items():
            with self.subTest(contract=name):
                self.assertEqual([], CONTRACTS.validate(name, payload))

    def test_missing_required_field(self):
        payload = dict(EXAMPLES["TableRef"])
        payload.pop("table")
        errors = CONTRACTS.validate("TableRef", payload)
        self.assertTrue(any("missing required field: table" in e for e in errors))

    def test_wrong_payload_type(self):
        errors = CONTRACTS.validate("Envelope", "not-an-object")
        self.assertEqual(["payload must be an object"], errors)

    def test_enum_is_enforced(self):
        payload = dict(EXAMPLES["MetricDef"], status="live")
        errors = CONTRACTS.validate("MetricDef", payload)
        self.assertTrue(any("not in" in e for e in errors))

    def test_datetime_format_is_enforced(self):
        payload = dict(EXAMPLES["Envelope"], event_time="2026-11-11")
        errors = CONTRACTS.validate("Envelope", payload)
        self.assertTrue(any("ISO-8601" in e for e in errors))

    def test_array_item_type_is_enforced(self):
        payload = dict(EXAMPLES["MQL"], metrics=["ok", 42])
        errors = CONTRACTS.validate("MQL", payload)
        self.assertTrue(any("metrics[1]" in e for e in errors))

    def test_unknown_contract(self):
        self.assertEqual(["unknown contract: Nope"], CONTRACTS.validate("Nope", {}))

    def test_schema_matches_spec(self):
        schema = CONTRACTS.schema("Envelope")
        self.assertEqual("Envelope", schema["title"])
        self.assertIn("source_id", schema["required"])
        self.assertEqual("object", schema["properties"]["payload"]["type"])
        self.assertEqual(7, len(CONTRACTS.names()))


if __name__ == "__main__":
    unittest.main()
