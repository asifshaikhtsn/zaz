import json
import os
import tempfile
import unittest
from pathlib import Path
from zaz import parse_proxy, source_url, select_for_test, publish


class FakeGeo:
    def country(self, ip):
        class Country:
            iso_code = {"8.8.8.8": "US", "1.1.1.1": "AU", "9.9.9.9": "DE"}.get(ip)
        class Record:
            country = Country()
        return Record()


class ZazTests(unittest.TestCase):
    def test_public_ip_only(self):
        self.assertEqual(parse_proxy("8.8.8.8:8080"), "8.8.8.8:8080")
        for s in ("10.0.0.1:80", "127.0.0.1:80", "8.8.8.8:0",
                  "8.8.8.8:99999", "localhost:80"):
            self.assertIsNone(parse_proxy(s))

    def test_branches(self):
        self.assertIn("/master/country/", source_url("asifshaikhtsn/shaikh", "US", "http"))
        self.assertIn("/main/country/", source_url("asifshaikhtsn/Walla", "US", "http"))

    def test_country_allowlist(self):
        items = {("http", "8.8.8.8:80"), ("http", "1.1.1.1:80"),
                 ("http", "9.9.9.9:80")}
        chosen = select_for_test(items, FakeGeo(), {"US", "DE"}, 10)
        self.assertEqual({c[0] for c in chosen}, {"US", "DE"})

    def test_publish_rejects_empty_and_preserves_old(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.getcwd()
            os.chdir(d)
            try:
                Path("country/US").mkdir(parents=True)
                Path("country/US/http.txt").write_text("old:80\n")
                with self.assertRaises(RuntimeError):
                    publish(set(), {}, 1)
                self.assertEqual(Path("country/US/http.txt").read_text(), "old:80\n")
                publish({("US", "http", "8.8.8.8:80")}, {}, 1)
                self.assertEqual(json.loads(Path("last_run.json").read_text())["stored_count"], 1)
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
