import unittest

from mosaic_device_slice.pipeline import decode_frames, version_binding_check
from mosaic_device_slice.registry import ProtocolRegistry, decode_values
from mosaic_device_slice.simulator import fault_events, simulate


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = ProtocolRegistry.load()

    def test_v1_battery_scale(self):
        self.assertEqual(42.0, self.registry.decode_value("dbc.v1", "battery_voltage", 420)["value"])

    def test_v2_battery_scale_changes_meaning(self):
        self.assertEqual(21.0, self.registry.decode_value("dbc.v2", "battery_voltage", 420)["value"])

    def test_default_rule_applies_to_unknown_signal(self):
        decoded = self.registry.decode_value("dbc.v1", "signal_03", 123)
        self.assertEqual(12.3, decoded["value"])
        self.assertEqual("raw", decoded["unit"])

    def test_out_of_range_is_marked_not_dropped(self):
        decoded = self.registry.decode_value("dbc.v1", "battery_voltage", 700)
        self.assertEqual("suspect", decoded["quality"])
        self.assertEqual(70.0, decoded["value"])

    def test_unknown_version_raises(self):
        with self.assertRaises(KeyError):
            self.registry.decode_value("dbc.v9", "battery_voltage", 1)

    def test_frame_uses_its_own_protocol_version(self):
        frame = {"device_id": "veh-0001", "ts": "2026-11-11T06:00:00Z", "protocol": "dbc.v2", "signals": {"battery_voltage": 420}}
        rows = self.registry.decode_frame(frame)
        self.assertEqual("dbc.v2", rows[0]["protocol_version"])
        self.assertEqual(21.0, rows[0]["value"])


class SimulatorTest(unittest.TestCase):
    def test_frame_and_signal_counts(self):
        frames = simulate(devices=3, frames=4, signals=10)
        self.assertEqual(12, len(frames))
        self.assertEqual(10, len(frames[0]["signals"]))
        self.assertEqual("dbc.v1", frames[0]["protocol"])

    def test_deterministic_with_same_seed(self):
        self.assertEqual(simulate(seed=7), simulate(seed=7))
        self.assertNotEqual(simulate(seed=7), simulate(seed=8))

    def test_injected_faults(self):
        frames = simulate(devices=10, frames=10, signals=50)
        registry = ProtocolRegistry.load()
        events = []
        for frame in frames:
            values = decode_values(frame, registry)
            events.extend(fault_events(frame, values))
        self.assertEqual(2, len(events))
        self.assertEqual({"P0A1", "P0A2"}, {event["fault_code"] for event in events})
        self.assertEqual({"veh-0001", "veh-0002"}, {event["device_id"] for event in events})

    def test_fault_event_id_is_stable(self):
        frames = simulate(devices=1, frames=6, signals=5)
        registry = ProtocolRegistry.load()
        frame = frames[-1]
        values = decode_values(frame, registry)
        self.assertEqual(fault_events(frame, values), fault_events(frame, values))


class SliceTest(unittest.TestCase):
    def test_decode_all_frames_to_long_rows(self):
        frames = simulate(devices=2, frames=3, signals=10)
        registry = ProtocolRegistry.load()
        rows, events = decode_frames(frames, registry)
        self.assertEqual(2 * 3 * 10, len(rows))
        self.assertEqual({"dbc.v1"}, {row["protocol_version"] for row in rows})
        self.assertTrue(all(row["codec_version"] == "codec-1" for row in rows))

    def test_version_binding_differs_on_same_bytes(self):
        frames = simulate(devices=1, frames=1, signals=5)
        registry = ProtocolRegistry.load()
        check = version_binding_check(frames[0], registry)
        self.assertTrue(check["differs"])
        self.assertEqual(42.0, check["v1_value"])
        self.assertEqual(21.0, check["v2_value"])


if __name__ == "__main__":
    unittest.main()
