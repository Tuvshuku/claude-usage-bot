"""Regression cases for transcript accounting and published API rates."""

import copy
import itertools
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collector


NOW = 1_800_001_800.0


def record(output=100, model="claude-sonnet-5", **usage):
    return {
        "type": "assistant", "requestId": "request", "timestamp": NOW - 60,
        "sessionId": "session", "message": {
            "id": "message", "model": model,
            "usage": {"input_tokens": 10, "output_tokens": output, **usage},
        },
    }


class AccountingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        patcher = patch.object(collector, "PROJECTS_DIR", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.state = collector.new_state()
        self.cfg = copy.deepcopy(collector.DEFAULT_CONFIG)
        self.cfg["live_sync"] = False

    def scan(self, name, *records):
        path = self.root / name
        path.write_text("".join(json.dumps(r) + "\n" for r in records))
        os.utime(path, (NOW, NOW))
        return collector.scan(self.state, self.cfg, NOW)

    def today(self):
        return collector.build_snapshot(self.state, self.cfg, NOW)["today"]

    def test_sonnet5_rate_does_not_increase_in_september(self):
        for timestamp in (1_780_000_000, NOW):
            cost, known = collector.cost_of({"claude-sonnet-5|standard": [1_000_000] * 5 + [1]}, timestamp)
            self.assertAlmostEqual(cost, 18.7)  # 2 + 10 + 2.5 + 4 + .2
            self.assertTrue(known)

    def test_fable51_and_mythos51_have_their_own_cache_read_rate(self):
        for model in ("claude-fable-5-1", "claude-mythos-5-1"):
            cost, known = collector.cost_of({model + "|standard": [1_000_000] * 5 + [1]}, NOW)
            self.assertAlmostEqual(cost, 92.75)  # 10 + 50 + 12.5 + 20 + .25
            self.assertTrue(known)

    def test_unknown_model_keeps_cost_estimated(self):
        self.scan("a.jsonl", record(model="claude-future"))
        self.assertFalse(self.today()["cost_exact"])

    def test_copy_without_http_id_is_not_counted_twice(self):
        original = record()
        copied = copy.deepcopy(original)
        copied.pop("requestId")
        self.scan("a.jsonl", original)
        self.state = json.loads(json.dumps(self.state))
        self.assertEqual(self.scan("copy.jsonl", copied), 0)
        self.assertEqual(self.today()["tokens"], 110)

    def test_distinct_messages_sharing_http_id_are_counted(self):
        second = record()
        second["message"]["id"] = "second-message"
        self.scan("a.jsonl", record(), second)
        self.assertEqual(self.today()["tokens"], 220)

    def test_cache_tier_refinement_cannot_duplicate_tokens_even_after_replay(self):
        partial = record(output=5, cache_creation_input_tokens=1000)
        final = record(cache_creation_input_tokens=1000,
                       cache_creation={"ephemeral_1h_input_tokens": 1000})
        self.scan("a.jsonl", partial)
        self.assertFalse(self.today()["cost_exact"])
        self.scan("b.jsonl", final)
        self.scan("c.jsonl", partial)
        today = self.today()
        self.assertEqual(today["tokens"], 1110)
        self.assertEqual(today["token_breakdown"]["cache_write_5m_tokens"], 0)
        self.assertEqual(today["token_breakdown"]["cache_write_1h_tokens"], 1000)
        self.assertEqual(today["cost_usd"], .005)
        self.assertTrue(today["cost_exact"])

    def test_partial_cache_split_preserves_unclassified_tokens(self):
        self.scan("a.jsonl", record(cache_creation_input_tokens=1000,
                                   cache_creation={"ephemeral_1h_input_tokens": 400}))
        today = self.today()
        self.assertEqual(today["tokens"], 1110)
        self.assertEqual(today["token_breakdown"]["cache_write_5m_tokens"], 600)
        self.assertFalse(today["cost_exact"])

    def test_partial_cache_details_improve_without_losing_known_hour_tokens(self):
        initial = record(cache_creation_input_tokens=1000)
        refined = record(cache_creation_input_tokens=1000,
                         cache_creation={"ephemeral_1h_input_tokens": 400})
        for order in itertools.permutations((initial, refined)):
            self.state = collector.new_state()
            self.scan("a.jsonl", *order)
            self.assertEqual(self.today()["token_breakdown"]["cache_write_1h_tokens"], 400)
            self.assertEqual(self.today()["tokens"], 1110)

    def test_billing_metadata_survives_iteration_upgrade_and_replayed_partial(self):
        partial = record(output=5, model="claude-opus-5", input_tokens=1_000_000,
                         inference_geo="us", speed="fast",
                         server_tool_use={"web_search_requests": 2})
        final = record(output=100, model="claude-opus-5", input_tokens=1_000_000,
                       inference_geo="not_available", iterations=[
                           {"input_tokens": 1_000_000, "output_tokens": 100},
                       ])
        final["timestamp"] += 10
        for order in itertools.permutations((partial, final)):
            self.state = collector.new_state()
            self.scan("a.jsonl", *order)
            self.assertEqual(self.today()["cost_usd"], 11.0255)
            self.assertEqual(self.today()["tokens"], 1_000_100)

    def test_older_geo_record_cannot_overwrite_final_geo(self):
        initial = record(input_tokens=1_000_000, inference_geo="global")
        final = record(input_tokens=1_000_000, inference_geo="us")
        final["timestamp"] += 10
        for order in itertools.permutations((initial, final)):
            self.state = collector.new_state()
            self.scan("a.jsonl", *order)
            self.assertEqual(self.today()["cost_usd"], 2.2011)

    def test_invalid_iteration_counts_do_not_erase_valid_top_level_counts(self):
        for value in (None, True, "broken", -1, float("inf")):
            parsed = collector.extract_usage(record(iterations=[
                {"input_tokens": value, "output_tokens": value},
            ]))
            self.assertEqual(parsed[3], [10, 100, 0, 0, 0])

    def test_compaction_usage_replaces_top_level_and_ignores_thinking_subtotal(self):
        self.scan("a.jsonl", record(output=5))
        final = record(iterations=[
            {"type": "compaction", "input_tokens": 180000, "output_tokens": 3500},
            {"type": "message", "input_tokens": 10, "output_tokens": 100},
        ], output_tokens_details={"thinking_tokens": 50})
        self.scan("b.jsonl", final)
        self.scan("copy.jsonl", final, record(output=5))
        today = self.today()
        self.assertEqual(today["tokens"], 183610)
        self.assertEqual(today["cost_usd"], .396)
        snap = collector.build_snapshot(self.state, self.cfg, NOW)
        self.assertEqual(sum(snap["sparkline"]), 183610)
        self.assertEqual(snap["gauges"][0]["used"], 183610)

    def test_iterations_charge_each_model_at_its_own_rate(self):
        final = record(input_tokens=2010, output=300, iterations=[
            {"model": None, "input_tokens": 10, "output_tokens": 100},
            {"model": "claude-fable-5-1", "input_tokens": 2000, "output_tokens": 200},
        ])
        self.scan("a.jsonl", record(output=5), final)
        today = self.today()
        self.assertEqual(today["tokens"], 2310)
        self.assertEqual(today["cost_usd"], .031)
        # Both the hourly rollups and partial-hour boundary path agree.
        for start, end in ((NOW - 120, NOW), (NOW - collector.HOUR, NOW + collector.HOUR)):
            totals = collector.window_totals(self.state["hours"], start, end, self.cfg,
                                             fable_only=True, requests=self.state["requests"])
            self.assertEqual(collector.metric_of(collector.totals_of(totals), "total"), 2200)
            cost, known = collector.window_cost(self.state, start, end, self.cfg, NOW, fable_only=True)
            self.assertAlmostEqual(cost, .03)
            self.assertTrue(known)

    def test_final_fast_speed_is_kept_when_older_standard_record_replays(self):
        partial = record(output=5, model="claude-opus-5", speed="standard", input_tokens=0)
        final = record(output=1_000_000, model="claude-opus-5", speed="fast", input_tokens=0)
        final["timestamp"] += 10
        self.scan("a.jsonl", partial)
        self.scan("b.jsonl", final)
        self.scan("copy.jsonl", partial)
        self.assertEqual(self.today()["cost_usd"], 50)
        self.assertEqual(len(self.state["hours"][str(int(NOW // collector.HOUR) * collector.HOUR)]), 1)

    def test_data_residency_and_search_fees_are_preserved(self):
        self.scan("a.jsonl", record(model="claude-opus-5", input_tokens=1_000_000,
                                   output=0, inference_geo="us",
                                   server_tool_use={"web_search_requests": 2, "web_fetch_requests": 3}))
        self.assertEqual(self.today()["cost_usd"], 5.52)
        self.assertTrue(self.today()["cost_exact"])

    def test_unpriced_server_tool_marks_cost_incomplete(self):
        self.scan("a.jsonl", record(server_tool_use={"code_execution_requests": 1}))
        self.assertFalse(self.today()["cost_exact"])

    def test_empty_or_malformed_iterations_use_top_level(self):
        for iterations in ([], None, "bad", [{"type": "message"}], [None]):
            parsed = collector.extract_usage(record(iterations=iterations))
            self.assertEqual(parsed[3], [10, 100, 0, 0, 0])

    def test_schema5_upgrade_rebuilds_old_counts(self):
        old = {"version": 5, "requests": {"old-id": []}, "last_live": {"gauges": {}}}
        with patch.object(Path, "exists", return_value=True), patch.object(
            Path, "read_text", return_value=json.dumps(old)
        ):
            state = collector.load_state()
        self.assertEqual(state["requests"], {})
        self.assertEqual(state["last_live"], old["last_live"])
