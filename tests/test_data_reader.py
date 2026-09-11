import json
import tempfile
import unittest
from pathlib import Path

from online_routing.data_reader import read_demands, read_topology


class DataReaderTests(unittest.TestCase):
    def test_rejects_malformed_topology_schemas(self):
        valid = {"nodes": ["A", "B"], "links": [{"source": "A", "target": "B", "capacity": 3}]}
        invalid_inputs = [
            [], {}, {**valid, "nodes": []}, {**valid, "nodes": ["A", "A"]},
            {**valid, "nodes": ["A", None]}, {**valid, "nodes": ["A", {}]},
            {**valid, "nodes": ["A", " "]}, {**valid, "directed": "false"},
            {**valid, "links": {}}, {**valid, "links": [None]},
            {**valid, "links": [{"source": "A", "target": "Z", "capacity": 3}]},
            {**valid, "links": [{"source": "A", "target": "A", "capacity": 3}]},
        ]
        for capacity in (0, -1, True, "3", None, float("inf"), float("nan")):
            invalid_inputs.append({**valid, "links": [{"source": "A", "target": "B", "capacity": capacity}]})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            for data in invalid_inputs:
                with self.subTest(data=data):
                    path.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        read_topology(path)

    def test_rejects_malformed_demands_and_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text(json.dumps({"nodes": ["A", "B"], "links": []}), encoding="utf-8")
            topology = read_topology(path)
            demand = {"id": "d", "source": "A", "target": "B", "bandwidth": 1}
            invalid_inputs = [
                {}, [None], [{}], [demand, demand],
                [{**demand, "source": "unknown"}], [{**demand, "target": "A"}],
                [{**demand, "id": None}], [{**demand, "id": ""}],
            ]
            for bandwidth in (0, -1, True, "1", None, float("inf"), float("nan")):
                invalid_inputs.append([{**demand, "bandwidth": bandwidth}])
            for data in invalid_inputs:
                with self.subTest(data=data):
                    path.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        read_demands(path, topology)

    def test_integer_identifiers_and_directed_reverse_arcs_are_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text(json.dumps({
                "nodes": [10, 20], "directed": True, "links": [
                    {"source": 10, "target": 20, "capacity": 2},
                    {"source": 20, "target": 10, "capacity": 3},
                ],
            }), encoding="utf-8")
            topology = read_topology(path)
            path.write_text(json.dumps([
                {"id": 9, "source": 10, "target": 20, "bandwidth": 1},
            ]), encoding="utf-8")
            demands = read_demands(path, topology)
            self.assertEqual(topology.nodes, ("10", "20"))
            self.assertEqual(len(topology.links), 2)
            self.assertTrue(topology.directed)
            self.assertEqual((demands[0].id, demands[0].source, demands[0].target), ("9", "10", "20"))

    def test_invalid_utf8_is_reported_as_a_read_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_bytes(b"\xff\xfeinvalid")
            with self.assertRaisesRegex(ValueError, "não foi possível ler"):
                read_topology(path)

    def test_reads_topology_and_preserves_demand_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topology_path = root / "topology.json"
            demands_path = root / "demands.json"
            topology_path.write_text(json.dumps({
                "nodes": ["A", "B"],
                "links": [{"source": "A", "target": "B", "capacity": 3}],
            }), encoding="utf-8")
            demands_path.write_text(json.dumps([
                {"id": "second-name", "source": "A", "target": "B", "bandwidth": 1},
                {"id": "first-name", "source": "A", "target": "B", "bandwidth": 1},
            ]), encoding="utf-8")

            topology = read_topology(topology_path)
            demands = read_demands(demands_path, topology)

        self.assertFalse(topology.directed)
        self.assertEqual([d.id for d in demands], ["second-name", "first-name"])

    def test_rejects_duplicate_undirected_link(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "topology.json"
            path.write_text(json.dumps({
                "nodes": ["A", "B"],
                "links": [
                    {"source": "A", "target": "B", "capacity": 3},
                    {"source": "B", "target": "A", "capacity": 3},
                ],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicado"):
                read_topology(path)


if __name__ == "__main__":
    unittest.main()
