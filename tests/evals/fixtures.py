"""Twenty small, deterministic coding tasks used by the evaluation runner.

The start SHA is the commit hash of the buggy baseline.  It is stored in
``start_shas.json`` so a fixture cannot silently drift between runs.
"""
from dataclasses import dataclass, replace
import json
from pathlib import Path


@dataclass(frozen=True)
class Fixture:
    id: str
    title: str
    source: str
    fixed_source: str
    test: str
    start_sha: str = ""

    def files(self, fixed: bool = False) -> dict[str, str]:
        return {
            "solution.py": self.fixed_source if fixed else self.source,
            "test_solution.py": self.test,
        }


_CASES = (
    Fixture("RSP-001", "Boş listede ilk eleman", """def first(items):
    return items[0]
""", """def first(items):
    return items[0] if items else None
""", """import unittest
from solution import first

class TestFirst(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(first([]))
    def test_value(self):
        self.assertEqual(first([7]), 7)
"""),
    Fixture("RSP-002", "Kapsayıcı toplam aralığı", """def sum_to(n):
    return sum(range(n))
""", """def sum_to(n):
    return sum(range(n + 1))
""", """import unittest
from solution import sum_to

class TestSumTo(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(sum_to(0), 0)
    def test_inclusive(self):
        self.assertEqual(sum_to(5), 15)
"""),
    Fixture("RSP-003", "Boşlukları normalize et", """def normalize(text):
    return text.strip()
""", """def normalize(text):
    return " ".join(text.split())
""", """import unittest
from solution import normalize

class TestNormalize(unittest.TestCase):
    def test_collapses(self):
        self.assertEqual(normalize("  a   b  "), "a b")
"""),
    Fixture("RSP-004", "Sıfıra bölmeyi reddet", """def safe_divide(a, b):
    return a / b
""", """def safe_divide(a, b):
    return None if b == 0 else a / b
""", """import unittest
from solution import safe_divide

class TestDivide(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(safe_divide(8, 2), 4)
    def test_zero(self):
        self.assertIsNone(safe_divide(1, 0))
"""),
    Fixture("RSP-005", "Değişken varsayılan argüman", """def append_item(value, items=[]):
    items.append(value)
    return items
""", """def append_item(value, items=None):
    if items is None:
        items = []
    items.append(value)
    return items
""", """import unittest
from solution import append_item

class TestAppend(unittest.TestCase):
    def test_no_leak(self):
        self.assertEqual(append_item(1), [1])
        self.assertEqual(append_item(2), [2])
"""),
    Fixture("RSP-006", "Negatif değeri sıfıra sabitle", """def parse_nonnegative(text):
    return int(text)
""", """def parse_nonnegative(text):
    return max(0, int(text))
""", """import unittest
from solution import parse_nonnegative

class TestParse(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(parse_nonnegative("7"), 7)
    def test_negative(self):
        self.assertEqual(parse_nonnegative("-3"), 0)
"""),
    Fixture("RSP-007", "Eksik anahtar için varsayılan", """def get_or_default(data, key, default):
    return data[key]
""", """def get_or_default(data, key, default):
    return data.get(key, default)
""", """import unittest
from solution import get_or_default

class TestDefault(unittest.TestCase):
    def test_present(self):
        self.assertEqual(get_or_default({"a": 1}, "a", 0), 1)
    def test_missing(self):
        self.assertEqual(get_or_default({}, "a", 42), 42)
"""),
    Fixture("RSP-008", "Yaşa göre sırala", """def sort_people(people):
    return sorted(people, key=lambda person: person["name"])
""", """def sort_people(people):
    return sorted(people, key=lambda person: person["age"])
""", """import unittest
from solution import sort_people

class TestSort(unittest.TestCase):
    def test_age(self):
        people = [{"name": "A", "age": 30}, {"name": "B", "age": 20}]
        self.assertEqual([p["age"] for p in sort_people(people)], [20, 30])
"""),
    Fixture("RSP-009", "Negatif sayfa ofseti", """def page_items(items, offset, limit):
    return items[offset:offset + limit]
""", """def page_items(items, offset, limit):
    offset = max(0, offset)
    return items[offset:offset + limit]
""", """import unittest
from solution import page_items

class TestPage(unittest.TestCase):
    def test_negative(self):
        self.assertEqual(page_items([1, 2, 3], -2, 2), [1, 2])
    def test_normal(self):
        self.assertEqual(page_items([1, 2, 3], 1, 1), [2])
"""),
    Fixture("RSP-010", "Yüzdeyi iki basamağa yuvarla", """def percent(value, total):
    return round(value * 100 / total, 0)
""", """def percent(value, total):
    return round(value * 100 / total, 2)
""", """import unittest
from solution import percent

class TestPercent(unittest.TestCase):
    def test_precision(self):
        self.assertEqual(percent(1, 3), 33.33)
"""),
    Fixture("RSP-011", "Slug noktalama temizliği", """def slugify(text):
    return text.lower().replace(" ", "-")
""", """import re

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
""", """import unittest
from solution import slugify

class TestSlug(unittest.TestCase):
    def test_punctuation(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")
"""),
    Fixture("RSP-012", "Deneme numaraları", """def attempt_numbers(max_tries):
    return list(range(max_tries - 1))
""", """def attempt_numbers(max_tries):
    return list(range(max_tries))
""", """import unittest
from solution import attempt_numbers

class TestAttempts(unittest.TestCase):
    def test_count(self):
        self.assertEqual(attempt_numbers(3), [0, 1, 2])
"""),
    Fixture("RSP-013", "İç içe eksik anahtar", """def nested_get(data, keys):
    return data[keys[0]][keys[1]]
""", """def nested_get(data, keys):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current
""", """import unittest
from solution import nested_get

class TestNested(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(nested_get({"a": {"b": 2}}, ["a", "b"]), 2)
    def test_missing(self):
        self.assertIsNone(nested_get({"a": {}}, ["a", "b"]))
"""),
    Fixture("RSP-014", "Alt sınırı uygula", """def clamp(value, low, high):
    return min(value, high)
""", """def clamp(value, low, high):
    return max(low, min(value, high))
""", """import unittest
from solution import clamp

class TestClamp(unittest.TestCase):
    def test_low(self):
        self.assertEqual(clamp(-1, 0, 10), 0)
    def test_high(self):
        self.assertEqual(clamp(11, 0, 10), 10)
"""),
    Fixture("RSP-015", "Sırayı koruyarak tekilleştir", """def unique(items):
    return sorted(set(items))
""", """def unique(items):
    return list(dict.fromkeys(items))
""", """import unittest
from solution import unique

class TestUnique(unittest.TestCase):
    def test_order(self):
        self.assertEqual(unique(["b", "a", "b"]), ["b", "a"])
"""),
    Fixture("RSP-016", "Parça boyutu", """def chunk(items, size):
    return [items[i:i + size] for i in range(0, len(items), size + 1)]
""", """def chunk(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]
""", """import unittest
from solution import chunk

class TestChunk(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])
"""),
    Fixture("RSP-017", "Çift uzunlukta medyan", """def median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2]
""", """def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
""", """import unittest
from solution import median

class TestMedian(unittest.TestCase):
    def test_odd(self):
        self.assertEqual(median([3, 1, 2]), 2)
    def test_even(self):
        self.assertEqual(median([1, 3]), 2)
"""),
    Fixture("RSP-018", "Tırnaklı CSV alanı", """def parse_csv_line(line):
    return line.split(",")
""", """import csv
import io

def parse_csv_line(line):
    return next(csv.reader(io.StringIO(line)))
""", """import unittest
from solution import parse_csv_line

class TestCsv(unittest.TestCase):
    def test_quoted_comma(self):
        self.assertEqual(parse_csv_line('a,"b,c",d'), ["a", "b,c", "d"])
"""),
    Fixture("RSP-019", "Kısaltma son eki", """def truncate(text, limit):
    return text[:limit]
""", """def truncate(text, limit):
    if len(text) <= limit:
        return text
    return text[:max(0, limit - 3)] + "..."
""", """import unittest
from solution import truncate

class TestTruncate(unittest.TestCase):
    def test_short(self):
        self.assertEqual(truncate("abc", 5), "abc")
    def test_long(self):
        self.assertEqual(truncate("abcdef", 5), "ab...")
"""),
    Fixture("RSP-020", "Birleştirirken girdiyi değiştirme", """def merge(left, right):
    left.update(right)
    return left
""", """def merge(left, right):
    return {**left, **right}
""", """import unittest
from solution import merge

class TestMerge(unittest.TestCase):
    def test_no_mutation(self):
        left = {"a": 1}
        self.assertEqual(merge(left, {"b": 2}), {"a": 1, "b": 2})
        self.assertEqual(left, {"a": 1})
"""),
)


def all_fixtures() -> tuple[Fixture, ...]:
    path = Path(__file__).with_name("start_shas.json")
    shas = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return tuple(replace(case, start_sha=shas.get(case.id, "")) for case in _CASES)


def by_id(task_id: str) -> Fixture:
    return next(case for case in all_fixtures() if case.id == task_id)