import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *arguments, environment=None):
        env = os.environ.copy()
        env.update(environment or {})
        return subprocess.run(
            [sys.executable, "-m", "online_routing", *map(str, arguments)],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10, check=False,
        )

    def test_external_directed_unicode_files_and_decimal_capacity(self):
        with tempfile.TemporaryDirectory(prefix="routing-external-") as directory:
            topology = Path(directory) / "rede externa.json"
            demands = Path(directory) / "pedidos.json"
            topology.write_text(json.dumps({
                "nodes": ["São Paulo", "東京"], "directed": True,
                "links": [{"source": "São Paulo", "target": "東京", "capacity": 0.3}],
            }, ensure_ascii=False), encoding="utf-8-sig")
            demands.write_text(json.dumps([
                {"id": "z", "source": "São Paulo", "target": "東京", "bandwidth": 0.1},
                {"id": "a", "source": "São Paulo", "target": "東京", "bandwidth": 0.2},
                {"id": "r", "source": "東京", "target": "São Paulo", "bandwidth": 0.1},
            ], ensure_ascii=False), encoding="utf-8")
            run = self.run_cli("--topology", topology, "--demands", demands,
                               environment={"PYTHONIOENCODING": "cp1252"})
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout.decode("utf-8"))
        self.assertEqual(result["configuration"]["processing_order"], ["z", "a", "r"])
        for name in ("shortest_path", "heuristic"):
            self.assertEqual(result[name]["metrics"], {
                "total_demands": 3, "accepted_demands": 2, "rejected_demands": 1,
                "total_hops": 2, "average_hops": 1.0, "maximum_link_utilization": 1.0,
            })
            self.assertEqual(result[name]["decisions"][0]["path"], ["São Paulo", "東京"])
            self.assertIn("não existe caminho topológico", result[name]["decisions"][2]["reason"])

    def test_documented_example_is_byte_deterministic_between_processes(self):
        arguments = ("--topology", ROOT / "examples/topology.json",
                     "--demands", ROOT / "examples/demands.json",
                     "--alpha", 1, "--beta", 5, "--candidates", 8)
        first = self.run_cli(*arguments, environment={"PYTHONHASHSEED": "1"})
        second = self.run_cli(*arguments, environment={"PYTHONHASHSEED": "987654"})
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        result = json.loads(first.stdout.decode("utf-8"))
        report = (ROOT / "REPORT.md").read_text(encoding="utf-8")
        for name, hops, average, utilization in (
            ("shortest_path", 4, 4 / 3, 1.0), ("heuristic", 5, 5 / 3, 0.6),
        ):
            self.assertEqual(result[name]["metrics"], {
                "total_demands": 4, "accepted_demands": 3, "rejected_demands": 1,
                "total_hops": hops, "average_hops": average,
                "maximum_link_utilization": utilization,
            })
            actual = result[name]["metrics"]
            label = "Caminho mínimo" if name == "shortest_path" else "Heurística"
            average_text = f'{actual["average_hops"]:.4f}'.replace(".", ",")
            row = (
                f'| {label} | {actual["accepted_demands"]} | {actual["rejected_demands"]} '
                f'| {actual["total_hops"]} | {average_text} '
                f'| {actual["maximum_link_utilization"]:.0%} |'
            )
            self.assertIn(row, report)
        self.assertEqual(result["shortest_path"]["decisions"][1]["path"], ["A", "B", "D"])
        self.assertEqual(result["heuristic"]["decisions"][1]["path"], ["A", "C", "E", "D"])
        self.assertEqual(result["heuristic"]["decisions"][1]["score"], 5.0)

    def test_cli_configuration_is_used(self):
        run = self.run_cli("--topology", ROOT / "examples/topology.json",
                           "--demands", ROOT / "examples/demands.json",
                           "--alpha", 2, "--beta", 0, "--candidates", 1)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout.decode("utf-8"))
        self.assertEqual(result["configuration"]["alpha"], 2)
        self.assertEqual(result["configuration"]["beta"], 0)
        self.assertEqual(result["configuration"]["candidate_limit"], 1)
        self.assertEqual(result["heuristic"]["metrics"], result["shortest_path"]["metrics"])
        self.assertEqual(result["heuristic"]["decisions"][1]["score"], 4.0)

    def test_cli_errors_have_code_two_and_no_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            malformed = Path(directory) / "malformed.json"
            malformed.write_text('{"nodes":', encoding="utf-8")
            for topology, options in (
                (malformed, ()), (Path(directory) / "missing.json", ()),
                (ROOT / "examples/topology.json", ("--alpha", "nan")),
                (ROOT / "examples/topology.json", ("--candidates", "0")),
            ):
                with self.subTest(topology=topology, options=options):
                    run = self.run_cli("--topology", topology,
                                       "--demands", ROOT / "examples/demands.json", *options)
                    self.assertEqual(run.returncode, 2, run.stderr)
                    self.assertEqual(run.stdout, b"")
                    self.assertIn(b"Erro:", run.stderr)
                    self.assertNotIn(b"Traceback", run.stderr)


if __name__ == "__main__":
    unittest.main()
