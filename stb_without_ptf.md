# spot_the_bug rows with no derived predict_the_fix

22 published `spot_the_bug` exercises (`status` in `in_review`/`live`) have no `predict_the_fix` row whose `source.derived_from.id` points at them. Generated from the live database, not the batch JSON files (D-90/D-91).

4 of the 22 are `origin="llm"` and have **no recoverable `fixed_code`** (D-90: that text was never persisted for LLM-generated rows and is permanently lost — only its sha256 remains). Those 4 cannot be hand-authored against via `pipeline/ptf_ingest.py` (it requires `grading.artifacts.fixed_code`); they are listed for completeness, flagged, with `buggy_code`/`test_code` still dumped.

## Summary table

| exercise id | version | concept | origin | fixed_code available |
|---|---|---|---|---|
| `6117f5d6-09e6-482b-aaba-8c219d5bc95b` | 1 | mutable-default-arg | handauthored_claude | yes |
| `79463928-f9c3-490a-86b4-0c246f2b3017` | 1 | shallow-vs-deep-copy | handauthored_claude | yes |
| `8ccfcfed-c436-4f1d-9030-0cfebaa47ce4` | 1 | truthy-falsy-empty-check | handauthored_claude | yes |
| `0434600e-b232-4e35-814e-ead0d323b49e` | 1 | is-vs-equality | handauthored_claude | yes |
| `d1d1ed31-d667-4ce2-ae92-56e0bb6f2a7e` | 1 | key-function-misuse | handauthored_claude | yes |
| `64ead3a0-3682-4e8e-a73f-8451d33e56a9` | 1 | float-precision | handauthored_claude | yes |
| `bed3af5f-8e18-4893-bd9a-126ef560f718` | 1 | is-vs-equality | handauthored_claude | yes |
| `4e41ec9e-fff9-445e-940c-b8fd4344e2b7` | 1 | global-state-mutation | handauthored_claude | yes |
| `2fe2b7c2-3979-4088-9e4c-878f25826c77` | 1 | off-by-one-slicing | handauthored_claude | yes |
| `b3567247-a647-4269-a925-8789aab6338f` | 1 | list-mutation-during-iteration | handauthored_claude | yes |
| `17d4aceb-adeb-46f1-a38f-2c9969705c75` | 1 | dict-mutation-during-iteration | handauthored_claude | yes |
| `878953f9-64ef-4abd-9dc1-4680c601ead3` | 1 | string-formatting-mismatch | handauthored_claude | yes |
| `4f1eb607-79ea-409b-85ce-3a03fb690cbb` | 1 | memoization-cache-staleness | handauthored_claude | yes |
| `8b2a18e6-54f2-4168-b86f-9ffa5374181f` | 1 | encoding-decoding-mismatch | handauthored_claude | yes |
| `6c542755-4a3d-4134-97d3-6dbe5b744707` | 1 | closure-late-binding | handauthored_claude | yes |
| `a1a8833a-7f39-4cd9-a526-9a844f3e2219` | 1 | mutable-default-arg | handauthored_claude | yes |
| `5876c089-5e1a-4988-a490-264964a2bde6` | 1 | string-vs-bytes-confusion | handauthored_claude | yes |
| `f4fb97c6-3d86-40e3-bb49-77fd8c00e0cf` | 1 | timezone-naive-vs-aware | handauthored_claude | yes |
| `dbd2f905-058d-473d-8a0f-7725d6393a13` | 1 | integer-division-truncation | llm | **NO — lost, see D-90** |
| `1b77eca4-eeb3-4a6f-8948-1403bfdc4799` | 1 | list-mutation-during-iteration | llm | **NO — lost, see D-90** |
| `1e117b13-c64d-46b6-bcdc-de44fda1509c` | 1 | closure-late-binding | llm | **NO — lost, see D-90** |
| `1803aa12-10cd-47c2-8e6d-1efbf2f7362d` | 1 | integer-division-truncation | llm | **NO — lost, see D-90** |

## Per-exercise dump

### `6117f5d6-09e6-482b-aaba-8c219d5bc95b` v1 — mutable-default-arg (handauthored_claude)

difficulty_authored: 3

context_note: Records events for an audit trail. Called once per request.

**buggy_code**

```python
def record_event(name, payload, history=[]):
    entry = {"name": name, "payload": payload}
    history.append(entry)
    if len(history) > 100:
        history.pop(0)
    return history


def summarize(history):
    return [item["name"] for item in history]
```

**fixed_code**

```python
def record_event(name, payload, history=None):
    if history is None:
        history = []
    entry = {"name": name, "payload": payload}
    history.append(entry)
    if len(history) > 100:
        history.pop(0)
    return history


def summarize(history):
    return [item["name"] for item in history]
```

**test_code**

```python
record_event("login", {"user": 1})
result = summarize(record_event("logout", {"user": 1}))
print(repr(result))
assert result == ["logout"], "a call without a history should start empty"
```


### `79463928-f9c3-490a-86b4-0c246f2b3017` v1 — shallow-vs-deep-copy (handauthored_claude)

difficulty_authored: 6

context_note: Builds a per-tenant report template from a shared set of defaults.

**buggy_code**

```python
class TemplateStore:
    def __init__(self, defaults):
        self.defaults = defaults

    def clone(self):
        return dict(self.defaults)

    def customize(self, overrides):
        draft = self.clone()
        for key, value in overrides.items():
            if isinstance(value, dict):
                draft[key].update(value)
            else:
                draft[key] = value
        return draft
```

**fixed_code**

```python
class TemplateStore:
    def __init__(self, defaults):
        self.defaults = defaults

    def clone(self):
        return dict(self.defaults)

    def customize(self, overrides):
        draft = self.clone()
        for key, value in overrides.items():
            if isinstance(value, dict):
                draft[key] = {**draft[key], **value}
            else:
                draft[key] = value
        return draft
```

**test_code**

```python
store = TemplateStore({"header": {"color": "blue"}, "title": "Report"})
store.customize({"header": {"color": "red"}})
result = store.customize({"title": "Q3"})
print(repr(result))
assert result == {"header": {"color": "blue"}, "title": "Q3"}, "defaults survive an earlier customization"
```


### `8ccfcfed-c436-4f1d-9030-0cfebaa47ce4` v1 — truthy-falsy-empty-check (handauthored_claude)

difficulty_authored: 5

context_note: Resolves the retry limit for a route. Zero means the route is never retried.

**buggy_code**

```python
class RetryPolicy:
    def __init__(self, defaults):
        self.defaults = defaults

    def limit_for(self, route, overrides):
        configured = overrides.get(route)
        if not configured:
            return self.defaults["limit"]
        return configured

    def describe(self, route, overrides):
        return "{}:{}".format(route, self.limit_for(route, overrides))
```

**fixed_code**

```python
class RetryPolicy:
    def __init__(self, defaults):
        self.defaults = defaults

    def limit_for(self, route, overrides):
        configured = overrides.get(route)
        if configured is None:
            return self.defaults["limit"]
        return configured

    def describe(self, route, overrides):
        return "{}:{}".format(route, self.limit_for(route, overrides))
```

**test_code**

```python
policy = RetryPolicy({"limit": 3})
result = policy.describe("/checkout", {"/checkout": 0})
print(repr(result))
assert result == "/checkout:0", "an explicit zero is honoured"
```


### `0434600e-b232-4e35-814e-ead0d323b49e` v1 — is-vs-equality (handauthored_claude)

difficulty_authored: 5

context_note: Looks up an order by the identifier supplied in a request path.

**buggy_code**

```python
def find_matching_order(orders, target_id):
    for order in orders:
        if order["id"] is target_id:
            return order
    return None


def lookup_from_request(orders, raw_id):
    return find_matching_order(orders, int(raw_id))
```

**fixed_code**

```python
def find_matching_order(orders, target_id):
    for order in orders:
        if order["id"] == target_id:
            return order
    return None


def lookup_from_request(orders, raw_id):
    return find_matching_order(orders, int(raw_id))
```

**test_code**

```python
orders = [{"id": 1000, "total": 42}]
result = lookup_from_request(orders, "1000")
print(repr(result))
assert result == {"id": 1000, "total": 42}, "a parsed identifier matches by value"
```


### `d1d1ed31-d667-4ce2-ae92-56e0bb6f2a7e` v1 — key-function-misuse (handauthored_claude)

difficulty_authored: 4

context_note: Picks the hottest endpoint from a window of access-log entries.

**buggy_code**

```python
def tally(events):
    counts = {}
    for event in events:
        name = event["endpoint"]
        counts[name] = counts.get(name, 0) + 1
    return counts


def busiest_endpoint(events):
    counts = tally(events)
    if not counts:
        return None
    ranked = sorted(counts.items(), key=lambda pair: pair[0], reverse=True)
    return ranked[0][0]


def summary(events):
    return {
        "counts": tally(events),
        "busiest": busiest_endpoint(events),
    }
```

**fixed_code**

```python
def tally(events):
    counts = {}
    for event in events:
        name = event["endpoint"]
        counts[name] = counts.get(name, 0) + 1
    return counts


def busiest_endpoint(events):
    counts = tally(events)
    if not counts:
        return None
    ranked = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
    return ranked[0][0]


def summary(events):
    return {
        "counts": tally(events),
        "busiest": busiest_endpoint(events),
    }
```

**test_code**

```python
events = [
    {"endpoint": "/alpha"},
    {"endpoint": "/alpha"},
    {"endpoint": "/alpha"},
    {"endpoint": "/zulu"},
]
result = summary(events)["busiest"]
print(repr(result))
assert result == "/alpha", "the endpoint with the most hits should win"
```


### `64ead3a0-3682-4e8e-a73f-8451d33e56a9` v1 — float-precision (handauthored_claude)

difficulty_authored: 4

context_note: Checks a generated invoice against the total the customer was quoted.

**buggy_code**

```python
LINE_ITEMS = (
    ("shipping", 0.1),
    ("handling", 0.2),
)


def line_total(items):
    total = 0.0
    for _name, amount in items:
        total += amount
    return total


def reconciles(items, expected):
    total = line_total(items)
    return total == expected


def audit(items, expected):
    return {
        "total": line_total(items),
        "reconciles": reconciles(items, expected),
    }
```

**fixed_code**

```python
LINE_ITEMS = (
    ("shipping", 0.1),
    ("handling", 0.2),
)


def line_total(items):
    total = 0.0
    for _name, amount in items:
        total += amount
    return total


def reconciles(items, expected):
    total = line_total(items)
    return abs(total - expected) < 0.005


def audit(items, expected):
    return {
        "total": line_total(items),
        "reconciles": reconciles(items, expected),
    }
```

**test_code**

```python
result = audit(LINE_ITEMS, 0.3)["reconciles"]
print(repr(result))
assert result is True, "the line items should reconcile against the quoted total"
```


### `bed3af5f-8e18-4893-bd9a-126ef560f718` v1 — is-vs-equality (handauthored_claude)

difficulty_authored: 4

context_note: Finds where a given row sits inside a freshly parsed table.

**buggy_code**

```python
def find_row(rows, target):
    for position, row in enumerate(rows):
        if row is target:
            return position
    return -1


def parse_rows(raw):
    parsed = []
    for chunk in raw.split(";"):
        parsed.append([int(part) for part in chunk.split(",")])
    return parsed


def locate(raw, target):
    rows = parse_rows(raw)
    return {
        "rows": rows,
        "position": find_row(rows, target),
    }
```

**fixed_code**

```python
def find_row(rows, target):
    for position, row in enumerate(rows):
        if row == target:
            return position
    return -1


def parse_rows(raw):
    parsed = []
    for chunk in raw.split(";"):
        parsed.append([int(part) for part in chunk.split(",")])
    return parsed


def locate(raw, target):
    rows = parse_rows(raw)
    return {
        "rows": rows,
        "position": find_row(rows, target),
    }
```

**test_code**

```python
result = locate("1,2;3,4;5,6", [3, 4])["position"]
print(repr(result))
assert result == 1, "the matching row should be found by value"
```


### `4e41ec9e-fff9-445e-940c-b8fd4344e2b7` v1 — global-state-mutation (handauthored_claude)

difficulty_authored: 4

context_note: Layers a caller's settings on top of the service defaults before a run.

**buggy_code**

```python
BASE_CONFIG = {
    "retries": 3,
    "timeout": 30,
}


def with_overrides(overrides):
    config = BASE_CONFIG
    config.update(overrides)
    return config


def describe(config):
    parts = []
    for key in sorted(config):
        parts.append(key + "=" + str(config[key]))
    return " ".join(parts)


def run_twice(first, second):
    with_overrides(first)
    return describe(with_overrides(second))
```

**fixed_code**

```python
BASE_CONFIG = {
    "retries": 3,
    "timeout": 30,
}


def with_overrides(overrides):
    config = dict(BASE_CONFIG)
    config.update(overrides)
    return config


def describe(config):
    parts = []
    for key in sorted(config):
        parts.append(key + "=" + str(config[key]))
    return " ".join(parts)


def run_twice(first, second):
    with_overrides(first)
    return describe(with_overrides(second))
```

**test_code**

```python
result = run_twice({"retries": 9}, {})
print(repr(result))
assert result == "retries=3 timeout=30", "a later call should not inherit an earlier override"
```


### `2fe2b7c2-3979-4088-9e4c-878f25826c77` v1 — off-by-one-slicing (handauthored_claude)

difficulty_authored: 3

context_note: Splits a result set into equal-size pages for the API response.

**buggy_code**

```python
PAGE_SIZE = 3


def page(items, number):
    start = number * PAGE_SIZE
    end = start + PAGE_SIZE - 1
    return items[start:end]


def page_count(items):
    full, remainder = divmod(len(items), PAGE_SIZE)
    if remainder:
        return full + 1
    return full


def paginate(items):
    pages = []
    for number in range(page_count(items)):
        pages.append(page(items, number))
    return pages
```

**fixed_code**

```python
PAGE_SIZE = 3


def page(items, number):
    start = number * PAGE_SIZE
    end = start + PAGE_SIZE
    return items[start:end]


def page_count(items):
    full, remainder = divmod(len(items), PAGE_SIZE)
    if remainder:
        return full + 1
    return full


def paginate(items):
    pages = []
    for number in range(page_count(items)):
        pages.append(page(items, number))
    return pages
```

**test_code**

```python
result = paginate(["a", "b", "c", "d", "e", "f"])
print(repr(result))
assert result == [["a", "b", "c"], ["d", "e", "f"]], "every item should appear on exactly one page"
```


### `b3567247-a647-4269-a925-8789aab6338f` v1 — list-mutation-during-iteration (handauthored_claude)

difficulty_authored: 4

context_note: Cleans a batch of parsed spreadsheet rows before they are rendered.

**buggy_code**

```python
def drop_blank_rows(rows):
    kept = []
    for row in rows:
        if not row:
            rows.remove(row)
            continue
        kept.append(row)
    return kept


def label_rows(rows):
    labels = []
    for index, row in enumerate(rows):
        labels.append("row-" + str(index) + "-" + str(len(row)))
    return labels


def report(rows):
    kept = drop_blank_rows(rows)
    return {
        "kept": kept,
        "labels": label_rows(kept),
    }
```

**fixed_code**

```python
def drop_blank_rows(rows):
    kept = []
    for row in rows:
        if not row:
            continue
        kept.append(row)
    return kept


def label_rows(rows):
    labels = []
    for index, row in enumerate(rows):
        labels.append("row-" + str(index) + "-" + str(len(row)))
    return labels


def report(rows):
    kept = drop_blank_rows(rows)
    return {
        "kept": kept,
        "labels": label_rows(kept),
    }
```

**test_code**

```python
rows = [[1], [], [2], [3]]
result = report(rows)["kept"]
print(repr(result))
assert result == [[1], [2], [3]], "no populated row should be lost"
```


### `17d4aceb-adeb-46f1-a38f-2c9969705c75` v1 — dict-mutation-during-iteration (handauthored_claude)

difficulty_authored: 4

context_note: Keeps only the words that appear often enough to be worth reporting.

**buggy_code**

```python
def tally(words):
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return counts


def prune(counts, floor):
    kept = {}
    for key in counts:
        if counts[key] < floor:
            del counts[key]
            continue
        kept[key] = counts[key]
    return kept


def frequent(words, floor):
    return prune(tally(words), floor)
```

**fixed_code**

```python
def tally(words):
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return counts


def prune(counts, floor):
    kept = {}
    for key in counts:
        if counts[key] < floor:
            continue
        kept[key] = counts[key]
    return kept


def frequent(words, floor):
    return prune(tally(words), floor)
```

**test_code**

```python
try:
    result = frequent(["a", "a", "b", "c", "c", "c"], 2)
except RuntimeError:
    result = "iteration_failed"
print(repr(result))
assert result == {"a": 2, "c": 3}, "rare words should be pruned without disturbing the walk"
```


### `878953f9-64ef-4abd-9dc1-4680c601ead3` v1 — string-formatting-mismatch (handauthored_claude)

difficulty_authored: 3

context_note: Renders a leaderboard line for each competitor. Scores carry one decimal place.

**buggy_code**

```python
def render(row):
    return "%s scored %d" % (row["name"], row["score"])


def render_all(rows):
    lines = []
    for row in rows:
        lines.append(render(row))
    return lines


def scoreboard(rows):
    return {
        "lines": render_all(rows),
        "entries": len(rows),
    }
```

**fixed_code**

```python
def render(row):
    return "%s scored %.1f" % (row["name"], row["score"])


def render_all(rows):
    lines = []
    for row in rows:
        lines.append(render(row))
    return lines


def scoreboard(rows):
    return {
        "lines": render_all(rows),
        "entries": len(rows),
    }
```

**test_code**

```python
result = scoreboard([{"name": "ada", "score": 91.5}])["lines"]
print(repr(result))
assert result == ["ada scored 91.5"], "a half point should survive rendering"
```


### `4f1eb607-79ea-409b-85ce-3a03fb690cbb` v1 — memoization-cache-staleness (handauthored_claude)

difficulty_authored: 4

context_note: Prices an item at several customer tiers. The cache exists because base lookups are expensive.

**buggy_code**

```python
_CACHE = {}


def cache_key(item, multiplier):
    return item["sku"]


def price(item, multiplier):
    key = cache_key(item, multiplier)
    if key in _CACHE:
        return _CACHE[key]
    value = item["base"] * multiplier
    _CACHE[key] = value
    return value


def quote(item, multipliers):
    return [price(item, multiplier) for multiplier in multipliers]
```

**fixed_code**

```python
_CACHE = {}


def cache_key(item, multiplier):
    return item["sku"] + ":" + str(multiplier)


def price(item, multiplier):
    key = cache_key(item, multiplier)
    if key in _CACHE:
        return _CACHE[key]
    value = item["base"] * multiplier
    _CACHE[key] = value
    return value


def quote(item, multipliers):
    return [price(item, multiplier) for multiplier in multipliers]
```

**test_code**

```python
result = quote({"sku": "A1", "base": 10}, [1, 2])
print(repr(result))
assert result == [10, 20], "a different multiplier should be priced, not served from cache"
```


### `8b2a18e6-54f2-4168-b86f-9ffa5374181f` v1 — encoding-decoding-mismatch (handauthored_claude)

difficulty_authored: 4

context_note: Carries text over a byte channel and reads it back on the far side.

**buggy_code**

```python
def to_bytes(text):
    return text.encode("utf-8")


def to_text(data):
    return data.decode("latin-1")


def roundtrip(text):
    return to_text(to_bytes(text))


def audit(messages):
    lengths = []
    for message in messages:
        lengths.append(len(roundtrip(message)))
    return lengths
```

**fixed_code**

```python
def to_bytes(text):
    return text.encode("utf-8")


def to_text(data):
    return data.decode("utf-8")


def roundtrip(text):
    return to_text(to_bytes(text))


def audit(messages):
    lengths = []
    for message in messages:
        lengths.append(len(roundtrip(message)))
    return lengths
```

**test_code**

```python
result = audit(["caf\u00e9"])
print(repr(result))
assert result == [4], "a round trip should hand back what it was given"
```


### `6c542755-4a3d-4134-97d3-6dbe5b744707` v1 — closure-late-binding (handauthored_claude)

difficulty_authored: 4

context_note: Builds one transform per configured offset, then runs them all against a seed value.

**buggy_code**

```python
def make_steps(offsets):
    steps = []
    for offset in offsets:
        steps.append(lambda value: value + offset)
    return steps


def apply_steps(steps, seed):
    results = []
    for step in steps:
        results.append(step(seed))
    return results


def run_pipeline(offsets, seed):
    return apply_steps(make_steps(offsets), seed)
```

**fixed_code**

```python
def make_steps(offsets):
    steps = []
    for offset in offsets:
        steps.append(lambda value, offset=offset: value + offset)
    return steps


def apply_steps(steps, seed):
    results = []
    for step in steps:
        results.append(step(seed))
    return results


def run_pipeline(offsets, seed):
    return apply_steps(make_steps(offsets), seed)
```

**test_code**

```python
result = run_pipeline([1, 10], 0)
print(repr(result))
assert result == [1, 10], "each step should carry the offset it was built with"
```


### `a1a8833a-7f39-4cd9-a526-9a844f3e2219` v1 — mutable-default-arg (handauthored_claude)

difficulty_authored: 4

context_note: Collects the timing of each step of a request, so the slowest can be reported.

**buggy_code**

```python
def trace(name, duration, spans={}):
    spans[name] = duration
    return spans


def slowest(spans):
    if not spans:
        return None
    ranked = sorted(spans.items(), key=lambda pair: pair[1], reverse=True)
    return ranked[0][0]


def handle(name, duration):
    spans = trace(name, duration)
    return {
        "spans": spans,
        "slowest": slowest(spans),
    }
```

**fixed_code**

```python
def trace(name, duration, spans=None):
    if spans is None:
        spans = {}
    spans[name] = duration
    return spans


def slowest(spans):
    if not spans:
        return None
    ranked = sorted(spans.items(), key=lambda pair: pair[1], reverse=True)
    return ranked[0][0]


def handle(name, duration):
    spans = trace(name, duration)
    return {
        "spans": spans,
        "slowest": slowest(spans),
    }
```

**test_code**

```python
handle("warmup", 99)
result = handle("db", 5)["spans"]
print(repr(result))
assert result == {"db": 5}, "a new request should start with no spans"
```


### `5876c089-5e1a-4988-a490-264964a2bde6` v1 — string-vs-bytes-confusion (handauthored_claude)

difficulty_authored: 4

context_note: Prepares labels for a binary record format that budgets ten bytes per field.

**buggy_code**

```python
FIELD_BYTES = 10


def pack_field(text, limit):
    encoded = text.encode("utf-8")
    if len(text) > limit:
        return None
    return encoded


def pack(records):
    packed = []
    for record in records:
        label = record["label"]
        packed.append(pack_field(label, FIELD_BYTES))
    return packed
```

**fixed_code**

```python
FIELD_BYTES = 10


def pack_field(text, limit):
    encoded = text.encode("utf-8")
    if len(encoded) > limit:
        return None
    return encoded


def pack(records):
    packed = []
    for record in records:
        label = record["label"]
        packed.append(pack_field(label, FIELD_BYTES))
    return packed
```

**test_code**

```python
result = pack([{"label": "caf\u00e9-latte"}])[0]
print(repr(result))
assert result is None, "the label overruns a ten-byte field"
```


### `f4fb97c6-3d86-40e3-bb49-77fd8c00e0cf` v1 — timezone-naive-vs-aware (handauthored_claude)

difficulty_authored: 4

context_note: Reports how many minutes each job has left, given a start in the operator's zone and a deadline in UTC.

**buggy_code**

```python
import datetime

UTC = datetime.timezone.utc


def minutes_left(start_local, end_utc):
    start_utc = start_local.replace(tzinfo=UTC)
    gap = end_utc - start_utc
    return int(gap.total_seconds() // 60)


def schedule(jobs, end_utc):
    remaining = []
    for job in jobs:
        remaining.append(minutes_left(job["start"], end_utc))
    return remaining
```

**fixed_code**

```python
import datetime

UTC = datetime.timezone.utc


def minutes_left(start_local, end_utc):
    start_utc = start_local.astimezone(UTC)
    gap = end_utc - start_utc
    return int(gap.total_seconds() // 60)


def schedule(jobs, end_utc):
    remaining = []
    for job in jobs:
        remaining.append(minutes_left(job["start"], end_utc))
    return remaining
```

**test_code**

```python
east = datetime.timezone(datetime.timedelta(hours=5))
jobs = [{"start": datetime.datetime(2026, 1, 1, 12, 0, tzinfo=east)}]
deadline = datetime.datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
result = schedule(jobs, deadline)
print(repr(result))
assert result == [60], "noon in a plus-five zone is 07:00 UTC, one hour before the deadline"
```


### `dbd2f905-058d-473d-8a0f-7725d6393a13` v1 — integer-division-truncation (llm)

difficulty_authored: 2

context_note: Determines how many flags a post needs before entering the moderation queue based on recent posting volume.

**buggy_code**

```python
def calculate_flag_threshold(total_posts, moderation_level):
    # For a given number of posts and a moderation level,
    # return the number of flags required to trigger review.
    # Higher moderation levels are stricter (lower threshold).
    if moderation_level == 'strict':
        divisor = 5
    elif moderation_level == 'moderate':
        divisor = 10
    else:
        divisor = 20
    if total_posts == 0:
        return 1
    threshold = max(1, round(total_posts / divisor))
    return threshold
```

**fixed_code**

**MISSING — never persisted; see D-90 (origin="llm" fixed_code is permanently unrecoverable).**

**test_code**

```python
result = calculate_flag_threshold(17, 'moderate')
print(repr(result))
assert result == 2, "With 17 posts and moderate, should round to 2 (17/10=1.7 rounds to 2)."
```


### `1b77eca4-eeb3-4a6f-8948-1403bfdc4799` v1 — list-mutation-during-iteration (llm)

difficulty_authored: 4

context_note: Runs after a reconciliation attempt to remove all billing records not present in the reconciled set.

**buggy_code**

```python
def remove_unmatched_charges(billing_records, reconciled_ids):
    removed = []
    for rec in billing_records:
        if rec['charge_id'] not in reconciled_ids:
            billing_records.remove(rec)
            removed.append(rec)
    return removed

# Example usage:
# billing_records = [
#     {'charge_id': 'A1', 'amount': 100},
#     {'charge_id': 'B2', 'amount': 200},
#     {'charge_id': 'C3', 'amount': 300}
# ]
# reconciled_ids = {'A1', 'C3'}
# remove_unmatched_charges(billing_records, reconciled_ids)
```

**fixed_code**

**MISSING — never persisted; see D-90 (origin="llm" fixed_code is permanently unrecoverable).**

**test_code**

```python
billing_records = [
    {'charge_id': 'X1', 'amount': 50},
    {'charge_id': 'Y2', 'amount': 75},
    {'charge_id': 'Z3', 'amount': 125}
]
reconciled_ids = set()
result = remove_unmatched_charges(billing_records, reconciled_ids)
print(repr(result))
assert result == [
    {'charge_id': 'X1', 'amount': 50},
    {'charge_id': 'Y2', 'amount': 75},
    {'charge_id': 'Z3', 'amount': 125}
], "All unmatched charges should be removed, but mutating the list during iteration skips some records."
```


### `1e117b13-c64d-46b6-bcdc-de44fda1509c` v1 — closure-late-binding (llm)

difficulty_authored: 5

context_note: Used to generate per-zone shipping calculators at app startup based on configured base rates.

**buggy_code**

```python
def build_shipping_rate_calculators(zones, base_rates):
    calculators = {}
    for zone in zones:
        base_rate = base_rates.get(zone, 10.0)
        def calculator(weight):
            return base_rate + 1.5 * weight
        calculators[zone] = calculator
    return calculators

def calculate_total_shipping(order_items, calculators):
    total = 0.0
    for item in order_items:
        zone = item['zone']
        weight = item['weight']
        calculator = calculators[zone]
        total += calculator(weight)
    return round(total, 2)
```

**fixed_code**

**MISSING — never persisted; see D-90 (origin="llm" fixed_code is permanently unrecoverable).**

**test_code**

```python
zones = ['US', 'CA']
base_rates = {'US': 7.0, 'CA': 12.0}
calculators = build_shipping_rate_calculators(zones, base_rates)
order_items = [
    {'zone': 'US', 'weight': 2.0},   # Should use US: 7.0 + 1.5*2 = 10.0
    {'zone': 'CA', 'weight': 1.0},   # Should use CA: 12.0 + 1.5*1 = 13.5
]
result = calculate_total_shipping(order_items, calculators)
print(repr(result))
assert result == 23.5, "Each calculator must use its correct zone's base_rate, not the last one bound in the loop."
```


### `1803aa12-10cd-47c2-8e6d-1efbf2f7362d` v1 — integer-division-truncation (llm)

difficulty_authored: 7

context_note: Used in a batch job to calculate customer partial refunds for unused service periods.

**buggy_code**

```python
def calculate_partial_refund(order_total_cents, days_used, total_days):
    if not (0 <= days_used <= total_days):
        raise ValueError("Invalid number of days used")
    if total_days == 0:
        return 0
    unused_days = total_days - days_used
    # Refund is proportional to unused days
    refund = (order_total_cents * unused_days) // total_days
    return refund

def process_refunds(order_records):
    # order_records: list of dicts with 'order_total_cents', 'days_used', 'total_days'
    refunds = []
    for rec in order_records:
        try:
            refund = calculate_partial_refund(
                rec['order_total_cents'],
                rec['days_used'],
                rec['total_days']
            )
        except Exception:
            refund = None
        refunds.append(refund)
    return refunds
```

**fixed_code**

**MISSING — never persisted; see D-90 (origin="llm" fixed_code is permanently unrecoverable).**

**test_code**

```python
records = [{'order_total_cents': 1000, 'days_used': 7, 'total_days': 30}]
result = process_refunds(records)
print(repr(result))
assert result == [767], "Refund must be rounded to nearest cent, not truncated"
```

