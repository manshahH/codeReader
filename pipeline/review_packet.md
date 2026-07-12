# Review packet -- 77 pending exercise(s)

## Contents
1. predict_the_fix `ec7ad751-76f3-47d4-bb09-cfdb8012b66e` v1 (concepts=['off-by-one-slicing'], difficulty=10) -- clean
2. spot_the_bug `6d8ce525-1874-4f80-be07-23e7b73353ca` v1 (concepts=['off-by-one-slicing'], difficulty=10) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: bug_lines_claim_mismatch, explanation_mismatch
3. trace `3ef49680-3791-42a2-a61b-e16c4486c54f` v1 (concepts=['shared-class-attribute'], difficulty=4) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
4. trace `bb188a9b-182e-4f9d-a503-95a8d8e2e759` v1 (concepts=['generator-exhaustion'], difficulty=10) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
5. trace `f3f72878-0760-4ab4-91b3-f8391a1e4492` v1 (concepts=['integer-division-truncation'], difficulty=6) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
6. spot_the_bug `dbd2f905-058d-473d-8a0f-7725d6393a13` v1 (concepts=['integer-division-truncation'], difficulty=2) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
7. trace `5fd95bd2-72e6-4a10-9c7c-355f6e82981a` v1 (concepts=['closure-late-binding'], difficulty=9) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
8. trace `bab03791-a05e-4f53-8165-266f7473ae8e` v1 (concepts=['off-by-one'], difficulty=4) -- solver=pass | solver_confidence=1.0 | clean
9. spot_the_bug `1b77eca4-eeb3-4a6f-8948-1403bfdc4799` v1 (concepts=['list-mutation-during-iteration'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: bug_lines_claim_mismatch
10. trace `7fee57dc-7e3f-46c2-bff2-15f5c4a20a65` v1 (concepts=['context-manager-misuse'], difficulty=6) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
11. trace `3e89621c-bf49-4573-b540-98a4744b58db` v1 (concepts=['early-return-skipped-path'], difficulty=6) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
12. trace `48f53359-9d57-4c83-9fb1-3fd0f9d102ae` v1 (concepts=['key-function-misuse'], difficulty=10) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
13. trace `e187e8cf-6127-4350-a6f7-c52e8cd6a214` v1 (concepts=['float-precision'], difficulty=1) -- solver=pass | solver_confidence=1.0 | clean
14. trace `3024e685-99d4-4278-be05-464ad7aa0acb` v1 (concepts=['variable-shadowing'], difficulty=7) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
15. spot_the_bug `1e117b13-c64d-46b6-bcdc-de44fda1509c` v1 (concepts=['closure-late-binding'], difficulty=5) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: bug_lines_claim_mismatch, explanation_mismatch
16. trace `9c84fa22-3b71-474c-b11b-d867dae57a1e` v1 (concepts=['off-by-one-slicing'], difficulty=8) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
17. trace `5663857a-9678-4396-8fba-2deaa8e0dc31` v1 (concepts=['dict-mutation-during-iteration'], difficulty=7) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
18. spot_the_bug `1803aa12-10cd-47c2-8e6d-1efbf2f7362d` v1 (concepts=['integer-division-truncation'], difficulty=7) -- defect_audit=flag solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: bug_lines_claim_mismatch, explanation_mismatch, defect_audit=flag
19. trace `6bf398fe-ce6e-442a-ad96-fbac988a5cbc` v1 (concepts=['off-by-one-slicing'], difficulty=4) -- solver=pass | solver_confidence=1.0 | clean
20. trace `17c52ad1-6f96-4715-a017-98c6d26daf7e` v1 (concepts=['mutable-default-arg'], difficulty=10) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
21. trace `d8541a90-4ced-446d-831c-d4d5336dd594` v1 (concepts=['early-return-skipped-path'], difficulty=10) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
22. spot_the_bug `8ccfcfed-c436-4f1d-9030-0cfebaa47ce4` v1 (concepts=['truthy-falsy-empty-check'], difficulty=5) -- defect_audit=flag solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: defect_audit=flag
23. spot_the_bug `0434600e-b232-4e35-814e-ead0d323b49e` v1 (concepts=['is-vs-equality'], difficulty=5) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
24. spot_the_bug `778fd26c-3714-4ff1-9218-7804580ec519` v1 (concepts=['truthy-falsy-empty-check'], difficulty=3) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
25. predict_the_fix `21feb161-7469-4f66-b49a-7375c8090105` v1 (concepts=['string-immutability-misuse'], difficulty=3) -- clean
26. spot_the_bug `5f6bee89-3387-4339-9c8e-781500dd6cc2` v1 (concepts=['string-immutability-misuse'], difficulty=3) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
27. spot_the_bug `64ead3a0-3682-4e8e-a73f-8451d33e56a9` v1 (concepts=['float-precision'], difficulty=4) -- defect_audit=flag solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: defect_audit=flag
28. spot_the_bug `bed3af5f-8e18-4893-bd9a-126ef560f718` v1 (concepts=['is-vs-equality'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
29. spot_the_bug `4e41ec9e-fff9-445e-940c-b8fd4344e2b7` v1 (concepts=['global-state-mutation'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
30. predict_the_fix `e0a08ca9-1b0c-4d47-9e44-c9736eee40c8` v1 (concepts=['dataclass-mutable-default'], difficulty=5) -- clean
31. spot_the_bug `2fe2b7c2-3979-4088-9e4c-878f25826c77` v1 (concepts=['off-by-one-slicing'], difficulty=3) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
32. spot_the_bug `b3567247-a647-4269-a925-8789aab6338f` v1 (concepts=['list-mutation-during-iteration'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
33. spot_the_bug `4f1eb607-79ea-409b-85ce-3a03fb690cbb` v1 (concepts=['memoization-cache-staleness'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
34. spot_the_bug `8b2a18e6-54f2-4168-b86f-9ffa5374181f` v1 (concepts=['encoding-decoding-mismatch'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
35. predict_the_fix `e2ad0217-11bb-4dfe-87db-aa105c45920e` v1 (concepts=['integer-division-truncation'], difficulty=3) -- clean
36. spot_the_bug `3d0fd9e2-3c91-43a6-8e5c-7e4d2651a607` v1 (concepts=['integer-division-truncation'], difficulty=3) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
37. spot_the_bug `6c542755-4a3d-4134-97d3-6dbe5b744707` v1 (concepts=['closure-late-binding'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
38. spot_the_bug `546ba9d6-124b-4c35-a478-b2e1ce713a19` v1 (concepts=['shallow-vs-deep-copy'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
39. predict_the_fix `33635266-e3fe-4942-8f02-72c0e84784cc` v1 (concepts=['shallow-vs-deep-copy'], difficulty=4) -- clean
40. spot_the_bug `a1a8833a-7f39-4cd9-a526-9a844f3e2219` v1 (concepts=['mutable-default-arg'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
41. spot_the_bug `2e4c2d75-4ee3-4b3e-8ce2-4713c00e99f7` v1 (concepts=['off-by-one'], difficulty=3) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
42. predict_the_fix `0774a668-33fd-4c01-a1b3-8636359f0c12` v1 (concepts=['off-by-one'], difficulty=3) -- clean
43. spot_the_bug `5876c089-5e1a-4988-a490-264964a2bde6` v1 (concepts=['string-vs-bytes-confusion'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
44. spot_the_bug `20c12e7a-9a8a-4070-ba31-25b1be99da8e` v1 (concepts=['injection-string-concat'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
45. predict_the_fix `b8141641-db53-4982-a5bf-1386bac144a6` v1 (concepts=['injection-string-concat'], difficulty=4) -- clean
46. predict_the_fix `5207abba-151d-4d33-b3da-9343891beda6` v1 (concepts=['aliasing-vs-copy'], difficulty=4) -- clean
47. spot_the_bug `4a6ae494-205c-4dca-b97d-c631dee08e50` v1 (concepts=['aliasing-vs-copy'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
48. spot_the_bug `f4fb97c6-3d86-40e3-bb49-77fd8c00e0cf` v1 (concepts=['timezone-naive-vs-aware'], difficulty=4) -- defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean
49. trace `13d21d87-a378-4aa0-ae32-c807026e0d1d` v1 (concepts=['string-formatting-mismatch'], difficulty=7) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
50. trace `87e4d8b2-7507-4ce8-819b-eb232d049f75` v1 (concepts=['string-formatting-mismatch'], difficulty=1) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
51. trace `f5045866-9a31-4a5d-9306-16db39c62c04` v1 (concepts=['truthy-falsy-empty-check'], difficulty=5) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
52. trace `886a7841-e709-44cf-8230-af92ffc38017` v1 (concepts=['dict-mutation-during-iteration'], difficulty=3) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
53. trace `1d1bb4d1-36dc-4062-a9bc-fa9ae2a84dc3` v1 (concepts=['float-precision'], difficulty=2) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
54. trace `f7255949-1cde-4d12-95b6-0629d45fc3a8` v1 (concepts=['sorting-stability-assumption'], difficulty=5) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
55. trace `7e371553-e385-4d22-9768-ed8e7de2a4e1` v1 (concepts=['float-precision'], difficulty=1) -- solver=pass | solver_confidence=1.0 | clean
56. trace `75c67371-17ae-4b9c-861e-88d18820a14e` v1 (concepts=['global-state-mutation'], difficulty=2) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
57. trace `a2d3bf03-e388-48b8-be6d-64f4ccf9913c` v1 (concepts=['unpacking-order-assumption'], difficulty=5) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
58. trace `f073a006-c7c5-47e6-9f3a-b14b49532d88` v1 (concepts=['sorting-stability-assumption'], difficulty=1) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
59. trace `ce8e41c6-19c7-4cca-a59c-aff2c93eca30` v1 (concepts=['string-immutability-misuse'], difficulty=6) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
60. trace `e1fbb620-45e0-4b4b-8fb7-358374591171` v1 (concepts=['early-return-skipped-path'], difficulty=2) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
61. trace `cd585008-47f9-4c71-baf7-08e5c03ed583` v1 (concepts=['shallow-vs-deep-copy'], difficulty=7) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
62. trace `56d6854c-83e7-49ef-8ede-69c42dfacdae` v1 (concepts=['unpacking-order-assumption'], difficulty=8) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
63. trace `6ecc1d0e-c944-43d9-9748-fd5ad5403ecf` v1 (concepts=['shallow-vs-deep-copy'], difficulty=10) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
64. trace `b6626824-8b0b-4287-9d4b-19a7c4b8da36` v1 (concepts=['list-mutation-during-iteration'], difficulty=6) -- solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch
65. predict_the_fix `e28cc1a5-bb8a-46cc-9960-312e21c765f8` v1 (concepts=['mutable-default-arg'], difficulty=3) -- clean
66. predict_the_fix `df68ea78-f178-4a0c-941d-e5fcbca10b77` v1 (concepts=['shallow-vs-deep-copy'], difficulty=6) -- clean
67. predict_the_fix `9537ac46-2432-4894-a688-37727fc08442` v1 (concepts=['truthy-falsy-empty-check'], difficulty=5) -- clean
68. predict_the_fix `13c269b8-a496-4a1f-8ddf-3d1d5689f3d6` v1 (concepts=['key-function-misuse'], difficulty=4) -- clean
69. predict_the_fix `7307f9c7-a83a-45af-943c-819107bdd1d0` v1 (concepts=['is-vs-equality'], difficulty=4) -- clean
70. predict_the_fix `138177ad-9d73-4c35-8734-b34b719c4762` v1 (concepts=['global-state-mutation'], difficulty=4) -- clean
71. predict_the_fix `8692c4aa-9239-44d1-919d-3754d7d20486` v1 (concepts=['list-mutation-during-iteration'], difficulty=4) -- clean
72. predict_the_fix `c78d7841-f812-4c18-95b7-87321c7fa3ab` v1 (concepts=['dict-mutation-during-iteration'], difficulty=4) -- clean
73. predict_the_fix `f52e284c-d5aa-4229-8f33-c29dca9946e5` v1 (concepts=['string-formatting-mismatch'], difficulty=3) -- clean
74. predict_the_fix `241f86cd-c6e5-45f0-a5dd-bc92a4f52f63` v1 (concepts=['memoization-cache-staleness'], difficulty=4) -- clean
75. predict_the_fix `10900108-ac59-4861-83d2-372920a5c88e` v1 (concepts=['encoding-decoding-mismatch'], difficulty=4) -- clean
76. predict_the_fix `53c81087-ebe8-4712-bfda-488fac2e79f8` v1 (concepts=['mutable-default-arg'], difficulty=4) -- clean
77. predict_the_fix `23b69b00-043c-4a8a-a9af-786803b84ead` v1 (concepts=['string-vs-bytes-confusion'], difficulty=4) -- clean

---

### predict_the_fix -- `ec7ad751-76f3-47d4-bb09-cfdb8012b66e` v1
status=in_review difficulty=10 concepts=['off-by-one-slicing'] created_at=2026-07-12T02:05:02.870289+00:00
quality: clean

#### Code
```python
class Inventory:
    def __init__(self):
        self._items = []

    def add_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                self._items[i] = (iid, qty + quantity)
                return
        self._items.append((item_id, quantity))

    def remove_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                if qty <= quantity:
                    del self._items[i]
                else:
                    self._items[i] = (iid, qty - quantity)
                return True
        return False

    def list_items(self, offset=0, limit=None):
        if limit is None:
            return self._items[offset:]
        return self._items[offset:offset + limit - 1]

    def batch_update(self, updates):
        for item_id, delta in updates:
            if delta > 0:
                self.add_item(item_id, delta)
            else:
                self.remove_item(item_id, -delta)

    def summarize(self):
        summary = {}
        for item_id, qty in self._items:
            summary[item_id] = qty
        return summary

```
context: This code powers paginated inventory listing for the admin dashboard.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: class Inventory:
    def __init__(self):
        self._items = []

    def add_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                self._items[i] = (iid, qty + quantity)
                return
        self._items.append((item_id, quantity))

    def remove_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                if qty <= quantity:
                    del self._items[i]
                else:
                    self._items[i] = (iid, qty - quantity)
                return True
        return False

    def list_items(self, offset=0, limit=None):
        if limit is None:
            return self._items[offset:]
        return self._items[offset:(offset + limit - 1) + 0]

    def batch_update(self, updates):
        for item_id, delta in updates:
            if delta > 0:
                self.add_item(item_id, delta)
            else:
                self.remove_item(item_id, -delta)

    def summarize(self):
        summary = {}
        for item_id, qty in self._items:
            summary[item_id] = qty
        return summary

- **b**: class Inventory:
    def __init__(self):
        self._items = []

    def add_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                self._items[i] = (iid, qty + quantity)
                return
        self._items.append((item_id, quantity))

    def remove_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                if qty <= quantity:
                    del self._items[i]
                else:
                    self._items[i] = (iid, qty - quantity)
                return True
        return False

    def list_items(self, offset=0, limit=None):
        if limit is None:
            return self._items[offset:]
        if limit <= 0:
            return []
        return self._items[offset:offset + limit - 1]

    def batch_update(self, updates):
        for item_id, delta in updates:
            if delta > 0:
                self.add_item(item_id, delta)
            else:
                self.remove_item(item_id, -delta)

    def summarize(self):
        summary = {}
        for item_id, qty in self._items:
            summary[item_id] = qty
        return summary

- **c**: class Inventory:
    def __init__(self):
        self._items = []

    def add_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                self._items[i] = (iid, qty + quantity)
                return
        self._items.append((item_id, quantity))

    def remove_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                if qty <= quantity:
                    del self._items[i]
                else:
                    self._items[i] = (iid, qty - quantity)
                return True
        return False

    def list_items(self, offset=0, limit=None):
        if limit is None:
            return self._items[offset:]
        return self._items[offset:offset + limit]

    def batch_update(self, updates):
        for item_id, delta in updates:
            if delta > 0:
                self.add_item(item_id, delta)
            else:
                self.remove_item(item_id, -delta)

    def summarize(self):
        summary = {}
        for item_id, qty in self._items:
            summary[item_id] = qty
        return summary
 <-- correct
- **d**: class Inventory:
    def __init__(self):
        self._items = []

    def add_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                self._items[i] = (iid, qty + quantity)
                return
        self._items.append((item_id, quantity))

    def remove_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                if qty <= quantity:
                    del self._items[i]
                else:
                    self._items[i] = (iid, qty - quantity)
                return True
        return False

    def list_items(self, offset=0, limit=None):
        if limit is None:
            return self._items[offset:]
        return self._items[offset + 1:offset + limit]

    def batch_update(self, updates):
        for item_id, delta in updates:
            if delta > 0:
                self.add_item(item_id, delta)
            else:
                self.remove_item(item_id, -delta)

    def summarize(self):
        summary = {}
        for item_id, qty in self._items:
            summary[item_id] = qty
        return summary


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: None

#### Explanation
- summary: The bug is in list_items: the slice stops at offset + limit - 1, so if you ask for 3 items, you only get 2. This is a classic off-by-one error, because the end index in Python slicing is already exclusive, so subtracting 1 causes the last intended item to be omitted. This only affects calls where limit is provided.
- principle: When slicing with offsets and limits in Python, remember that the end index is exclusive; do not subtract one from limit.
- mismatch_flagged: False
- why_wrong:
  - **a**: Attempts to clarify or document the end index but does not change the off-by-one off the limit, so the bug remains.
  - **b**: Guards for non-positive limits but otherwise leaves the off-by-one error unchanged, so test still fails.
  - **d**: Adjusts the start index of the slice, but moves the offset ahead one too far, so returned items are still incorrect.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 46, in <module>
AssertionError: list_items(offset=1, limit=3) should return the next 3 items, not just 2

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 46, in <module>
AssertionError: list_items(offset=1, limit=3) should return the next 3 items, not just 2

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 48, in <module>
AssertionError: list_items(offset=1, limit=3) should return the next 3 items, not just 2

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 46, in <module>
AssertionError: list_items(offset=1, limit=3) should return the next 3 items, not just 2

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### spot_the_bug -- `6d8ce525-1874-4f80-be07-23e7b73353ca` v1
status=in_review difficulty=10 concepts=['off-by-one-slicing'] created_at=2026-07-12T02:05:02.870289+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: bug_lines_claim_mismatch, explanation_mismatch

#### Code
```python
class Inventory:
    def __init__(self):
        self._items = []

    def add_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                self._items[i] = (iid, qty + quantity)
                return
        self._items.append((item_id, quantity))

    def remove_item(self, item_id, quantity):
        for i, (iid, qty) in enumerate(self._items):
            if iid == item_id:
                if qty <= quantity:
                    del self._items[i]
                else:
                    self._items[i] = (iid, qty - quantity)
                return True
        return False

    def list_items(self, offset=0, limit=None):
        if limit is None:
            return self._items[offset:]
        return self._items[offset:offset + limit - 1]

    def batch_update(self, updates):
        for item_id, delta in updates:
            if delta > 0:
                self.add_item(item_id, delta)
            else:
                self.remove_item(item_id, -delta)

    def summarize(self):
        summary = {}
        for item_id, qty in self._items:
            summary[item_id] = qty
        return summary

```
context: This code powers paginated inventory listing for the admin dashboard.

#### Reason options
- **a**: list_items's limit parameter produces an off-by-one error, returning one fewer item than requested. <-- correct
- **b**: Using enumerate in add_item could skip elements if the list changes size during iteration.
- **c**: The summarize method mutates the internal list while iterating over it, risking RuntimeError.
- **d**: If remove_item is called for an item not present, it may raise an exception rather than return False.

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [25]
- correct_reason_id: a

#### Failing-test proof
```python
inv = Inventory()
inv.add_item('A', 10)
inv.add_item('B', 20)
inv.add_item('C', 30)
inv.add_item('D', 40)
result = inv.list_items(offset=1, limit=3)
print(repr(result))
assert result == [('B', 20), ('C', 30), ('D', 40)], "list_items(offset=1, limit=3) should return the next 3 items, not just 2"
```

#### Explanation
- summary: The bug is in list_items: the slice stops at offset + limit - 1, so if you ask for 3 items, you only get 2. This is a classic off-by-one error, because the end index in Python slicing is already exclusive, so subtracting 1 causes the last intended item to be omitted. This only affects calls where limit is provided.
- principle: When slicing with offsets and limits in Python, remember that the end index is exclusive; do not subtract one from limit.
- mismatch_flagged: True (draft_explanation.line_notes ([20]) does not reference the sandbox-verified bug_lines ([25]))

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 46, in <module>
AssertionError: list_items(offset=1, limit=3) should return the next 3 items, not just 2

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [25] (diff-derived); generator claimed [20]
- [x] stb_claim_matches_execution -- buggy: claimed "[('B', 20), ('C', 30)]" executed "[('B', 20), ('C', 30)]"; fixed: claimed "[('B', 20), ('C', 30), ('D', 40)]" executed "[('B', 20), ('C', 30), ('D', 40)]"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### trace -- `3ef49680-3791-42a2-a61b-e16c4486c54f` v1
status=in_review difficulty=4 concepts=['shared-class-attribute'] created_at=2026-07-12T02:06:39.311645+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
class TaxCalculator:
    default_rate = 0.15

    def __init__(self, rate=None):
        if rate is not None:
            self.rate = rate

    def calculate(self, amount):
        return amount * getattr(self, 'rate', TaxCalculator.default_rate)

    @classmethod
    def set_default_rate(cls, new_rate):
        cls.default_rate = new_rate

# Create two calculators, one with custom rate
c1 = TaxCalculator()
c2 = TaxCalculator(0.25)

print(c1.calculate(100))
print(c2.calculate(100))
TaxCalculator.set_default_rate(0.2)
print(c1.calculate(100))
print(c2.calculate(100))
```
context: Multiple TaxCalculator instances are used with both shared and instance rates.

#### Question
What does this code print?
#### Choices
- **a**: 15.0
25.0
20.0
25.0 <-- correct
- **b**: 15.0
25.0
20.0
20.0
- **c**: 15.0
25.0
15.0
25.0
- **d**: 15.0
15.0
20.0
20.0

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: '15.0\n25.0\n20.0\n25.0'

#### Explanation
- summary: First, c1 uses the class attribute default_rate (0.15), so 100*0.15=15.0. c2 was instantiated with rate=0.25, so it uses its own attribute (100*0.25=25.0). The class method then sets TaxCalculator.default_rate to 0.2, so c1 (which has no instance rate) now uses 100*0.2=20.0, but c2 still uses its own rate (100*0.25=25.0).
- principle: Instance attributes shadow class attributes; changing a class attribute only impacts instances without an instance-specific attribute of the same name.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output '15.0\n25.0\n20.0\n25.0'; the verified output is authoritative regardless)
- why_wrong:
  - **b**: This assumes set_default_rate updates all rates, even instance attributes, but it only updates the class attribute.
  - **d**: Assumes both instances always use the class attribute, ignoring that c2 has its own rate.
  - **c**: Assumes set_default_rate has no effect on future calculations, so c1 keeps using the old default rate.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='15.0\n25.0\n20.0\n25.0' expected_stdout='15.0\n25.0\n20.0\n25.0'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `bb188a9b-182e-4f9d-a503-95a8d8e2e759` v1
status=in_review difficulty=10 concepts=['generator-exhaustion'] created_at=2026-07-12T02:09:02.524598+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def find_renewable(subscriptions):
    for sub_id, active in subscriptions:
        if active:
            yield sub_id

def mark_and_iterate(renewable_ids):
    marks = []
    for sid in renewable_ids:
        if sid % 2 == 0:
            break
        marks.append(f"{sid}-checked")
    return marks

def count_active(renewable_ids):
    return sum(1 for _ in renewable_ids)

def process_subscriptions():
    data = [
        (101, True),
        (102, True),
        (103, False),
        (104, True),
        (105, True)
    ]
    gen = find_renewable(data)
    marks = mark_and_iterate(gen)
    print("Mark phase:", marks)
    count1 = count_active(gen)
    print("First count: ", count1)
    # New generator from same data
    gen2 = find_renewable(data)
    count2 = count_active(gen2)
    print("Second count: ", count2)

process_subscriptions()
```
context: Code traces active subscription renewals, then counts how many remain.

#### Question
What does this code print?
#### Choices
- **a**: Mark phase: ['101-checked']
First count:  4
Second count:  4
- **b**: Mark phase: ['101-checked']
First count:  2
Second count:  2
- **c**: Mark phase: ['101-checked']
First count:  2
Second count:  4 <-- correct
- **d**: Mark phase: ['101-checked', '102-checked', '104-checked', '105-checked']
First count:  2
Second count:  4

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: "Mark phase: ['101-checked']\nFirst count:  2\nSecond count:  4"

#### Explanation
- summary: The generator gen is advanced by mark_and_iterate until it hits an even id (102), so only 101 is marked. The generator is now at 103, since break happens after yielding 102. Since 103 is inactive, the next yielded values are 104 and 105, so count_active(gen) returns 2. count_active(gen2) counts all actives from a fresh generator, yielding 101, 102, 104, 105, thus 4.
- principle: Python generators are exhausted as you iterate them, and cannot be reused or restarted once consumed.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "Mark phase: ['101-checked']\nFirst count:  2\nSecond count:  4"; the verified output is authoritative regardless)
- why_wrong:
  - **a**: Assumes the generator starts over for count_active(gen), but it continues from its current position (after break), not from the beginning.
  - **d**: Assumes the mark_and_iterate function iterates through all items, not breaking at the first even id.
  - **b**: Assumes both generators somehow pick up after break, or count only the remaining items after mark_and_iterate for both generators, but gen2 is a fresh generator and should count all actives.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="Mark phase: ['101-checked']\nFirst count:  2\nSecond count:  4" expected_stdout="Mark phase: ['101-checked']\nFirst count:  2\nSecond count:  4"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `f3f72878-0760-4ab4-91b3-f8391a1e4492` v1
status=in_review difficulty=6 concepts=['integer-division-truncation'] created_at=2026-07-12T02:10:11.500586+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def calculate_boxes(order_qty, box_size):
    # Returns number of full boxes and leftover units
    full_boxes = order_qty // box_size
    leftovers = order_qty % box_size
    return full_boxes, leftovers

def fulfill_orders(orders, box_sizes):
    shipments = []
    for idx, qty in enumerate(orders):
        size = box_sizes[idx % len(box_sizes)]
        boxes, leftover = calculate_boxes(qty, size)
        # In some cases, small leftover amounts are promoted to a full box
        if leftover > 0 and leftover >= size // 3:
            boxes += 1
            leftover = 0
        shipments.append((boxes, leftover))
    return shipments

orders = [37, 48, 15, 59]
box_sizes = [12, 10]
results = fulfill_orders(orders, box_sizes)
for shipment in results:
    print(shipment)
```
context: Order fulfillment system: shipping quantities in boxes of alternating sizes.

#### Question
What does this code print?
#### Choices
- **a**: (3, 0)
(5, 0)
(1, 0)
(6, 0)
- **b**: (4, 1)
(5, 0)
(2, 3)
(6, 0)
- **c**: (3, 1)
(4, 8)
(1, 3)
(5, 9)
- **d**: (3, 1)
(5, 0)
(1, 3)
(6, 0) <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: '(3, 1)\n(5, 0)\n(1, 3)\n(6, 0)'

#### Explanation
- summary: Each order is paired with a box size, alternating from box_sizes. Integer division (//) is used to determine full boxes, and modulus (%) for leftovers. If the leftover is at least one third (using integer division size // 3) of the box size, the leftovers are promoted to a full box and leftover set to zero. This process is repeated for all four orders, and the results are printed as (boxes, leftover) tuples.
- principle: Integer division (//) truncates towards negative infinity, and all division/truncation in the code is strictly integer, so size // 3 produces a truncated integer threshold for promotion.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output '(3, 1)\n(5, 0)\n(1, 3)\n(6, 0)'; the verified output is authoritative regardless)
- why_wrong:
  - **c**: Misconception: Interpreted leftover >= size / 3 as float division, making the condition almost never true, so leftover is nearly always retained.
  - **b**: Misconception: Used float division for full_boxes, then truncated down, so number of boxes is greater when division is not exact.
  - **a**: Misconception: Promoted any leftover to a full box, ignoring the 'at least one third' threshold, causing all leftovers to be zero when there is any remainder.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='(3, 1)\n(5, 0)\n(1, 3)\n(6, 0)' expected_stdout='(3, 1)\n(5, 0)\n(1, 3)\n(6, 0)'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### spot_the_bug -- `dbd2f905-058d-473d-8a0f-7725d6393a13` v1
status=in_review difficulty=2 concepts=['integer-division-truncation'] created_at=2026-07-12T02:10:59.328527+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Determines how many flags a post needs before entering the moderation queue based on recent posting volume.

#### Reason options
- **a**: No bug: the code rounds post-count division properly and always returns an integer threshold. <-- correct
- **b**: Division truncates to integer, so the threshold will always be too low on non-multiples of divisor.
- **c**: round(total_posts / divisor) can return a float, so the threshold may not be an integer.
- **d**: When total_posts is zero, the code may attempt to divide by zero and raise an exception.

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: []
- correct_reason_id: a

#### Failing-test proof
```python
result = calculate_flag_threshold(17, 'moderate')
print(repr(result))
assert result == 2, "With 17 posts and moderate, should round to 2 (17/10=1.7 rounds to 2)."
```

#### Explanation
- summary: The code converts post counts and moderation levels into an integer threshold, using round() for non-integer division so it does not truncate. It always returns a minimum of 1, and never divides by zero because it guards for total_posts == 0. There is no bug.
- principle: Always guard for zero-division and use rounding if truncation is not desired.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_passes_test_when_no_bug
- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- diff says [], candidate says []

#### Semantic gate verdicts
- **defect_audit**: pass -- no defects on a has_bug=false candidate
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### trace -- `5fd95bd2-72e6-4a10-9c7c-355f6e82981a` v1
status=in_review difficulty=9 concepts=['closure-late-binding'] created_at=2026-07-12T02:11:41.258452+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def build_discount_rules():
    rules = []
    base_discounts = [
        ("A", 0.10),
        ("B", 0.20),
        ("C", 0.15)
    ]

    for name, pct in base_discounts:
        def rule(price):
            return (name, round(price * (1 - pct), 2))
        rules.append(rule)

    specials = [
        ("A", 50),
        ("B", 80)
    ]

    for name, min_price in specials:
        def special_rule(price):
            if price >= min_price:
                return (name + "-special", price - 5)
            else:
                return (name + "-special", price)
        rules.append(special_rule)

    return rules

def apply_all_rules(price):
    rules = build_discount_rules()
    results = []
    for r in rules:
        results.append(r(price))
    return results

finals = apply_all_rules(100)
for x in finals:
    print(x)
```
context: A pricing engine applies various discount and special markdown rules to a product.

#### Question
What does this code print?
#### Choices
- **a**: ('A', 90.0)
('A', 90.0)
('A', 90.0)
('A-special', 95)
('A-special', 95)
- **b**: ('C', 85.0)
('B', 80.0)
('A', 90.0)
('B-special', 95)
('A-special', 95)
- **c**: ('A', 90.0)
('B', 80.0)
('C', 85.0)
('A-special', 95)
('B-special', 95)
- **d**: ('B', 85.0)
('B', 85.0)
('B', 85.0)
('B-special', 95)
('B-special', 95) <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: "('B', 85.0)\n('B', 85.0)\n('B', 85.0)\n('B-special', 95)\n('B-special', 95)"

#### Explanation
- summary: The closures created inside the for loops (both for base discounts and specials) late-bind to the loop variables. By the time any of the rules are called, the loop variables 'name' and 'pct' for the first loop and 'name' and 'min_price' for the second loop have their final values ('B', 0.20) and ('B', 80), respectively. Thus, all three rule functions return ('B', 85.0) and both special_rule functions return ('B-special', 95) for input 100.
- principle: Python closures capture variables by reference, not by value; the variable's final value is used when the function is called, not when defined.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "('B', 85.0)\n('B', 85.0)\n('B', 85.0)\n('B-special', 95)\n('B-special', 95)"; the verified output is authoritative regardless)
- why_wrong:
  - **c**: Assumes each rule captures the value of the loop variable at its own iteration (early binding), so discounts are ('A', 90.0), ('B', 80.0), ('C', 85.0), and specials apply as intended.
  - **a**: Assumes all closures use the first value of the loop variable ('A'), so all rules use 'A' and its discount.
  - **b**: Misunderstands how closures or appending work, believing the rules are built in the loop's reversed order, so values are applied in reverse.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="('B', 85.0)\n('B', 85.0)\n('B', 85.0)\n('B-special', 95)\n('B-special', 95)" expected_stdout="('B', 85.0)\n('B', 85.0)\n('B', 85.0)\n('B-special', 95)\n('B-special', 95)"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `bab03791-a05e-4f53-8165-266f7473ae8e` v1
status=in_review difficulty=4 concepts=['off-by-one'] created_at=2026-07-12T02:12:53.117910+00:00
quality: solver=pass | solver_confidence=1.0 | clean

#### Code
```python
def deliver_webhooks(webhooks, max_attempts):
    delivered = []
    for i, webhook in enumerate(webhooks):
        attempts = 0
        while attempts < max_attempts:
            if webhook['should_fail'] and attempts < max_attempts - 1:
                attempts += 1
                continue
            delivered.append((webhook['id'], attempts + 1))
            break
    return delivered

webhooks = [
    {'id': 'A', 'should_fail': False},
    {'id': 'B', 'should_fail': True},
    {'id': 'C', 'should_fail': True},
]

result = deliver_webhooks(webhooks, 3)
print(result)
```
context: Delivering a batch of webhooks, each may fail a number of times before success.

#### Question
What does this code print?
#### Choices
- **a**: [('A', 1), ('B', 2), ('C', 2)]
- **b**: [('A', 1), ('B', 3), ('C', 2)]
- **c**: [('A', 1), ('B', 3), ('C', 3)] <-- correct
- **d**: [('A', 1), ('B', 1), ('C', 1)]

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: "[('A', 1), ('B', 3), ('C', 3)]"

#### Explanation
- summary: For webhook A, should_fail is False, so it is delivered on the first attempt. For B and C, should_fail is True, so the loop continues until attempts == max_attempts - 1 (attempts = 2), then on the 3rd attempt (attempts = 2, attempts + 1 = 3), the webhook is delivered. The final result is [('A', 1), ('B', 3), ('C', 3)].
- principle: Off-by-one errors commonly occur when using counters and termination conditions, especially around whether to use < or <=.
- mismatch_flagged: False
- why_wrong:
  - **a**: This assumes the webhook is delivered after max_attempts - 1 retries, but delivery actually occurs on the max_attempts-th attempt.
  - **d**: This assumes should_fail only applies to the first attempt, but the condition actually causes failure until the last attempt.
  - **b**: This stops retrying C one iteration early, as if the loop exits at attempts = max_attempts - 1 instead of when it reaches max_attempts.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="[('A', 1), ('B', 3), ('C', 3)]" expected_stdout="[('A', 1), ('B', 3), ('C', 3)]"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### spot_the_bug -- `1b77eca4-eeb3-4a6f-8948-1403bfdc4799` v1
status=in_review difficulty=4 concepts=['list-mutation-during-iteration'] created_at=2026-07-12T02:13:34.620274+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: bug_lines_claim_mismatch

#### Code
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
context: Runs after a reconciliation attempt to remove all billing records not present in the reconciled set.

#### Reason options
- **a**: The code mutates billing_records while iterating it, causing some unmatched records to be skipped and not removed. <-- correct
- **b**: The code fails to check for duplicate charge IDs, which could result in retaining duplicate records.
- **c**: The function returns None when no records are removed, which could lead to unexpected NoneType errors.
- **d**: The reconciled_ids argument is not copied, so changes to it in the function could leak outside.

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [3, 4, 5, 6]
- correct_reason_id: a

#### Failing-test proof
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

#### Explanation
- summary: The bug is caused by removing elements from billing_records while iterating over it, which alters the list indices during the loop. As a result, when two or more consecutive records are unmatched, the loop skips some of them and not all unmatched records are removed. This means the returned list of removed records is incomplete in these cases.
- principle: Never mutate a list while iterating over it; always collect targets for removal in a separate pass.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: All unmatched charges should be removed, but mutating the list during iteration skips some records.

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [3, 4, 5, 6] (diff-derived); generator claimed [3]
- [x] stb_claim_matches_execution -- buggy: claimed "[{'charge_id': 'X1', 'amount': 50}, {'charge_id': 'Z3', 'amount': 125}]" executed "[{'charge_id': 'X1', 'amount': 50}, {'charge_id': 'Z3', 'amount': 125}]"; fixed: claimed "[{'charge_id': 'X1', 'amount': 50}, {'charge_id': 'Y2', 'amount': 75}, {'charge_id': 'Z3', 'amount': 125}]" executed "[{'charge_id': 'X1', 'amount': 50}, {'charge_id': 'Y2', 'amount': 75}, {'charge_id': 'Z3', 'amount': 125}]"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### trace -- `7fee57dc-7e3f-46c2-bff2-15f5c4a20a65` v1
status=in_review difficulty=6 concepts=['context-manager-misuse'] created_at=2026-07-12T02:14:13.247357+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
class RateLimiter:
    def __init__(self, max_calls):
        self.max_calls = max_calls
        self.calls = 0
        self._locked = False

    def __enter__(self):
        if self._locked:
            raise Exception("Already acquired")
        self._locked = True
        if self.calls >= self.max_calls:
            self._locked = False
            raise Exception("Rate limit exceeded")
        self.calls += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._locked = False

limiter = RateLimiter(2)

for i in range(3):
    try:
        with limiter:
            print(f"Allowed {i}")
    except Exception as e:
        print(f"Denied {i} : {e}")
```
context: A RateLimiter context manager is used to control how many times an action can be taken.

#### Question
What does this code print?
#### Choices
- **a**: Allowed 0
Denied 1 : Rate limit exceeded
Denied 2 : Rate limit exceeded
- **b**: Allowed 0
Allowed 1
Allowed 2
- **c**: Allowed 0
Allowed 1
Denied 2 : Rate limit exceeded <-- correct
- **d**: Denied 0 : Rate limit exceeded
Denied 1 : Rate limit exceeded
Denied 2 : Rate limit exceeded

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: 'Allowed 0\nAllowed 1\nDenied 2 : Rate limit exceeded'

#### Explanation
- summary: The RateLimiter allows up to 2 successful entries. For i=0 and i=1, self.calls is less than max_calls, so 'Allowed 0' and 'Allowed 1' print. On i=2, self.calls is 2, so an exception is raised and 'Denied 2 : Rate limit exceeded' is printed.
- principle: A context manager does not automatically reset internal state between uses; unless explicitly reset, self.calls grows over time.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output 'Allowed 0\nAllowed 1\nDenied 2 : Rate limit exceeded'; the verified output is authoritative regardless)
- why_wrong:
  - **b**: Assumes the context manager resets self.calls on each __exit__, so the calls never exceed the limit.
  - **a**: Assumes the check for limit occurs after incrementing self.calls, so only first iteration is allowed; in reality, increment happens after the check.
  - **d**: Mistakenly thinks self.calls starts at the maximum, so all attempts raise immediately.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='Allowed 0\nAllowed 1\nDenied 2 : Rate limit exceeded' expected_stdout='Allowed 0\nAllowed 1\nDenied 2 : Rate limit exceeded'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `3e89621c-bf49-4573-b540-98a4744b58db` v1
status=in_review difficulty=6 concepts=['early-return-skipped-path'] created_at=2026-07-12T02:15:15.432413+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def calculate_shipping_rate(weight, expedited):
    if weight <= 0:
        return "Invalid weight"
    base_rate = 5
    # Free expedited for small packages
    if weight < 2 and expedited:
        return base_rate
    rate = base_rate + weight * 1.5
    if expedited:
        # Early return for heavy expedited
        if weight > 10:
            return rate + 20
        rate += 10
    else:
        # Discount for regular shipping if light
        if weight < 5:
            rate -= 2
    return rate

orders = [
    (1.5, True),    # small, expedited: triggers early return
    (3, False),     # small, not expedited: applies discount
    (12, True),     # heavy, expedited: early return with surcharge
    (7, False),     # medium, not expedited: no discount
]

for w, exp in orders:
    print(calculate_shipping_rate(w, exp))
```
context: A shipping rate calculator must handle early returns for specific cases (like heavy expedited orders or free expedited on small ones).

#### Question
What does this code print?
#### Choices
- **a**: 5
10.5
43.0
15.5
- **b**: 5
7.5
43.0
15.5 <-- correct
- **c**: 5
7.5
30.0
15.5
- **d**: 5
7.5
43.0
13.5

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: '5\n7.5\n43.0\n15.5'

#### Explanation
- summary: The function calculate_shipping_rate uses several early returns. For (1.5, True), it returns 5 due to the 'free expedited for small packages' branch. For (3, False), it falls through to apply the base, the weight, and the discount for light regular shipping, resulting in 7.5. For (12, True), the heavy expedited shipping triggers an early return with a 20 surcharge. For (7, False), it calculates the default rate with no discount.
- principle: Early return statements can cause later logic branches to be skipped entirely, which affects the output for specific cases.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output '5\n7.5\n43.0\n15.5'; the verified output is authoritative regardless)
- why_wrong:
  - **a**: Did not apply the -2 discount for (3, False); applied only base+weight.
  - **c**: Missed the early return for heavy expedited (12, True), so omitted the +20 surcharge.
  - **d**: Incorrectly applied the discount to (7, False) when weight >= 5 should not get it.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='5\n7.5\n43.0\n15.5' expected_stdout='5\n7.5\n43.0\n15.5'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `48f53359-9d57-4c83-9fb1-3fd0f9d102ae` v1
status=in_review difficulty=10 concepts=['key-function-misuse'] created_at=2026-07-12T02:18:12.421797+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
from typing import List, Dict

def webhook_deliveries():
    deliveries = [
        {'id': 1, 'status': 'pending', 'retry': 2, 'time': 100},
        {'id': 2, 'status': 'failed', 'retry': 1, 'time': 110},
        {'id': 3, 'status': 'pending', 'retry': 3, 'time': 90},
        {'id': 4, 'status': 'pending', 'retry': 1, 'time': 105},
        {'id': 5, 'status': 'failed', 'retry': 2, 'time': 95}
    ]
    
    def retry_priority(d):
        return d['retry'], d['time']
    
    def time_priority(d):
        return d['time'], d['retry']

    # Step 1: filter only pending
    pendings = [d for d in deliveries if d['status'] == 'pending']
    
    # Step 2: sort by retry asc, then time asc
    sorted_pendings = sorted(pendings, key=retry_priority)
    
    # Step 3: pick the one with min (time, retry)
    # (should use same key as sorted but intentionally use different one)
    chosen = min(sorted_pendings, key=time_priority)
    
    # Step 4: update status
    chosen['status'] = 'delivered'
    
    # Step 5: print the ids of items still pending, sorted by (retry, time)
    still_pending = [d for d in deliveries if d['status'] == 'pending']
    still_pending_sorted = sorted(still_pending, key=retry_priority)
    print([d['id'] for d in still_pending_sorted])
    
    # Step 6: print the id of the delivered one
    print(chosen['id'])
    
    # Step 7: print the original deliveries as list of (id, status) tuples in insertion order
    print([(d['id'], d['status']) for d in deliveries])

webhook_deliveries()
```
context: Webhook retry logic: filtering, sorting, and updating delivery task states.

#### Question
What does this code print?
#### Choices
- **a**: [1, 4]
4
[(1, 'pending'), (2, 'failed'), (3, 'pending'), (4, 'delivered'), (5, 'failed')]
- **b**: [4, 1]
3
[(1, 'pending'), (2, 'failed'), (3, 'delivered'), (4, 'pending'), (5, 'failed')] <-- correct
- **c**: [1, 3]
4
[(1, 'pending'), (2, 'failed'), (3, 'pending'), (4, 'delivered'), (5, 'failed')]
- **d**: [1, 3, 4]
3
[(1, 'pending'), (2, 'failed'), (3, 'delivered'), (4, 'pending'), (5, 'failed')]

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: "[4, 1]\n3\n[(1, 'pending'), (2, 'failed'), (3, 'delivered'), (4, 'pending'), (5, 'failed')]"

#### Explanation
- summary: First, only the 'pending' deliveries (1, 3, 4) are filtered. They are sorted by (retry, time) as [4, 1, 3]. The min() is called with a different key -- (time, retry), so among [4, 1, 3], delivery 3 (time=90, retry=3) is chosen because it has the smallest (time, retry) tuple. Its status is updated to 'delivered'. The remaining pending ones are 4 and 1, sorted as [4, 1] by (retry, time). So we print [4, 1], then the delivered id 3, and finally the full original deliveries list shows only 3's status changed.
- principle: If sorted() and min() use different key functions, the selected element may not be the first after sort.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "[4, 1]\n3\n[(1, 'pending'), (2, 'failed'), (3, 'delivered'), (4, 'pending'), (5, 'failed')]"; the verified output is authoritative regardless)
- why_wrong:
  - **a**: Assumes min() uses same key as sorted(), so picks id=4 (lowest retry=1, lowest time=105 among retry=1), and pending list is [1, 4], delivered id is 4.
  - **d**: Thinks all pending tasks remain pending after delivery (misses that one was delivered and filtered out), so outputs [1, 3, 4].
  - **c**: Mixes up the key order, using (time, retry) everywhere, so pending list is [1, 3].

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="[4, 1]\n3\n[(1, 'pending'), (2, 'failed'), (3, 'delivered'), (4, 'pending'), (5, 'failed')]" expected_stdout="[4, 1]\n3\n[(1, 'pending'), (2, 'failed'), (3, 'delivered'), (4, 'pending'), (5, 'failed')]"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `e187e8cf-6127-4350-a6f7-c52e8cd6a214` v1
status=in_review difficulty=1 concepts=['float-precision'] created_at=2026-07-12T02:19:05.693574+00:00
quality: solver=pass | solver_confidence=1.0 | clean

#### Code
```python
def allow_request(last_time, now, min_interval):
    if now - last_time >= min_interval:
        print("allowed")
    else:
        print("blocked")

last_time = 1.2
now = 1.7
min_interval = 0.5

allow_request(last_time, now, min_interval)
```
context: A rate limiter checks if enough time has passed between requests.

#### Question
What does this code print?
#### Choices
- **a**: blocked
allowed
- **b**: allowed <-- correct
- **c**: allowed
blocked
- **d**: blocked

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: 'allowed'

#### Explanation
- summary: The function allow_request computes now - last_time as 1.7 - 1.2, which is exactly 0.5 in binary floating point. Since 0.5 >= 0.5, the 'if' branch is executed and 'allowed' is printed. Only one print statement runs.
- principle: For most decimal fractions like 0.5, Python's float representation is exact, so basic comparisons work as expected.
- mismatch_flagged: False
- why_wrong:
  - **d**: Assumes Python float math yields a small error here, so 0.5 >= 0.5 is False and 'blocked' prints.
  - **c**: Thinks both print statements execute, misunderstanding the if-else control flow.
  - **a**: Believes the function is called twice, conflating possible outputs.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='allowed' expected_stdout='allowed'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `3024e685-99d4-4278-be05-464ad7aa0acb` v1
status=in_review difficulty=7 concepts=['variable-shadowing'] created_at=2026-07-12T02:20:34.010459+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
CATALOG = {
    "books": [
        {"id": 1, "title": "Python 101", "stock": 3},
        {"id": 2, "title": "Effective Java", "stock": 5},
        {"id": 3, "title": "Clean Code", "stock": 0},
    ]
}

def sync_stock(catalog, updates):
    # Intentionally shadowing 'books' and 'book' in nested scopes
    books = catalog["books"]
    for update in updates:
        for book in books:
            if book["id"] == update["id"]:
                book = book.copy()
                book["stock"] = update["stock"]
                books.append(book)
                break
    for book in books:
        print(f'{book["id"]}: {book["title"]} - stock {book["stock"]}')

def run_sync():
    updates = [
        {"id": 1, "stock": 7},
        {"id": 3, "stock": 12}
    ]
    # Intentionally shadowing variable in local scope
    catalog = {"books": [b.copy() for b in CATALOG["books"]]}
    sync_stock(catalog, updates)
    print("---")
    # Intentionally using the global 'CATALOG', not the local one
    for book in CATALOG["books"]:
        print(f'{book["id"]}: {book["title"]} - stock {book["stock"]}')

run_sync()
```
context: A sync job applies stock updates to a book catalog and reports both the synced and original data.

#### Question
What does this code print?
#### Choices
- **a**: 1: Python 101 - stock 7
2: Effective Java - stock 5
3: Clean Code - stock 12
---
1: Python 101 - stock 3
2: Effective Java - stock 5
3: Clean Code - stock 0
- **b**: 1: Python 101 - stock 3
2: Effective Java - stock 5
3: Clean Code - stock 0
1: Python 101 - stock 7
3: Clean Code - stock 12
---
1: Python 101 - stock 3
2: Effective Java - stock 5
3: Clean Code - stock 0 <-- correct
- **c**: 1: Python 101 - stock 7
2: Effective Java - stock 5
3: Clean Code - stock 12
---
1: Python 101 - stock 7
2: Effective Java - stock 5
3: Clean Code - stock 12
- **d**: 1: Python 101 - stock 3
2: Effective Java - stock 5
3: Clean Code - stock 0
---
1: Python 101 - stock 3
2: Effective Java - stock 5
3: Clean Code - stock 0

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: '1: Python 101 - stock 3\n2: Effective Java - stock 5\n3: Clean Code - stock 0\n1: Python 101 - stock 7\n3: Clean Code - stock 12\n---\n1: Python 101 - stock 3\n2: Effective Java - stock 5\n3: Clean Code - stock 0'

#### Explanation
- summary: In run_sync, we create a deep copy of the books list, so changes don't affect the original CATALOG. In sync_stock, for each update, we scan for a matching book, make a copy (shadowing 'book'), update its stock, and append it to the books list. The print loop in sync_stock thus prints originals plus new updated copies. The final print in run_sync prints the original catalog, unchanged.
- principle: Variable shadowing in Python can cause assignments to affect only local variables, and not mutate outer-scope or original data unless referenced directly.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output '1: Python 101 - stock 3\n2: Effective Java - stock 5\n3: Clean Code - stock 0\n1: Python 101 - stock 7\n3: Clean Code - stock 12\n---\n1: Python 101 - stock 3\n2: Effective Java - stock 5\n3: Clean Code - stock 0'; the verified output is authoritative regardless)
- why_wrong:
  - **c**: This assumes that assigning to 'book' in the inner loop updates the books list elements directly, but in reality, 'book' is shadowed and reassigned to a copy; only the new copies are modified and appended.
  - **a**: This is similar to b but misses that the print in sync_stock prints all books in the local catalog, including appended ones.
  - **d**: This ignores that the code appends the updated copies to the list, so sync_stock should print five books, not three.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='1: Python 101 - stock 3\n2: Effective Java - stock 5\n3: Clean Code - stock 0\n1: Python 101 - stock 7\n3: Clean Code - stock 12\n---\n1: Python 101 - stock 3\n2: Effective Java - stock 5\n3: Clean Code - stock 0' expected_stdout='1: Python 101 - stock 3\n2: Effective Java - stock 5\n3: Clean Code - stock 0\n1: Python 101 - stock 7\n3: Clean Code - stock 12\n---\n1: Python 101 - stock 3\n2: Effective Java - stock 5\n3: Clean Code - stock 0'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### spot_the_bug -- `1e117b13-c64d-46b6-bcdc-de44fda1509c` v1
status=in_review difficulty=5 concepts=['closure-late-binding'] created_at=2026-07-12T02:22:36.897982+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: bug_lines_claim_mismatch, explanation_mismatch

#### Code
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
context: Used to generate per-zone shipping calculators at app startup based on configured base rates.

#### Reason options
- **a**: All calculators end up using the final value of base_rate (closure late binding) rather than their own zone's rate. <-- correct
- **b**: The use of round(total, 2) in calculate_total_shipping causes precision loss for certain weights.
- **c**: The default base_rate of 10.0 in base_rates.get() will cause a KeyError if a zone is missing.
- **d**: The calculators dictionary is re-used across calls, causing state leakage between orders.

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [5, 6]
- correct_reason_id: a

#### Failing-test proof
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

#### Explanation
- summary: The bug is a classic closure late-binding problem: the inner calculator function closes over base_rate, but all created calculators share the same (last) value of base_rate. Thus, every zone's calculator uses the base_rate from the last zone in the loop, not its own. This only fails when different base rates per zone are used.
- principle: When defining closures in a loop, bind loop variables as default arguments or via a factory to avoid late binding issues.
- mismatch_flagged: True (draft_explanation.line_notes ([4]) does not reference the sandbox-verified bug_lines ([5, 6]))

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 27, in <module>
AssertionError: Each calculator must use its correct zone's base_rate, not the last one bound in the loop.

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [5, 6] (diff-derived); generator claimed [4]
- [x] stb_claim_matches_execution -- buggy: claimed '28.5' executed '28.5'; fixed: claimed '23.5' executed '23.5'

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### trace -- `9c84fa22-3b71-474c-b11b-d867dae57a1e` v1
status=in_review difficulty=8 concepts=['off-by-one-slicing'] created_at=2026-07-12T02:23:33.837334+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def reconcile_bills(invoices, payments):
    matched = []
    unmatched_invoices = invoices[:]
    unmatched_payments = payments[:]

    for i, inv in enumerate(invoices):
        # Try to find a payment for the invoice
        for j, pay in enumerate(unmatched_payments):
            if inv["amount"] == pay["amount"] and inv["ref"] == pay["ref"]:
                matched.append((inv, pay))
                # Remove matched invoice and payment
                unmatched_payments = unmatched_payments[:j] + unmatched_payments[j+1:]
                unmatched_invoices = unmatched_invoices[:i] + unmatched_invoices[i+1:]
                break

    # Slicing to get last 2 unmatched invoices and first 2 unmatched payments
    print("Unmatched invoices:", unmatched_invoices[-2:])
    print("Unmatched payments:", unmatched_payments[:2])
    print("Matched count:", len(matched))

invoices = [
    {"ref": "A100", "amount": 120},
    {"ref": "B200", "amount": 200},
    {"ref": "C300", "amount": 75},
    {"ref": "D400", "amount": 180},
    {"ref": "E500", "amount": 90}
]

payments = [
    {"ref": "A100", "amount": 120},
    {"ref": "C300", "amount": 75},
    {"ref": "E500", "amount": 90},
    {"ref": "F600", "amount": 50},
    {"ref": "B200", "amount": 200}
]

reconcile_bills(invoices, payments)
```
context: Reconciling billing records after payment imports, reporting unmatched and matched items.

#### Question
What does this code print?
#### Choices
- **a**: Unmatched invoices: [{'ref': 'B200', 'amount': 200}, {'ref': 'D400', 'amount': 180}]
Unmatched payments: [{'ref': 'F600', 'amount': 50}]
Matched count: 4 <-- correct
- **b**: Unmatched invoices: [{'ref': 'D400', 'amount': 180}]
Unmatched payments: [{'ref': 'F600', 'amount': 50}, {'ref': 'B200', 'amount': 200}]
Matched count: 4
- **c**: Unmatched invoices: [{'ref': 'D400', 'amount': 180}, {'ref': 'E500', 'amount': 90}]
Unmatched payments: [{'ref': 'F600', 'amount': 50}, {'ref': 'B200', 'amount': 200}]
Matched count: 3
- **d**: Unmatched invoices: [{'ref': 'D400', 'amount': 180}, {'ref': 'E500', 'amount': 90}]
Unmatched payments: [{'ref': 'F600', 'amount': 50}, {'ref': 'B200', 'amount': 200}]
Matched count: 4

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: "Unmatched invoices: [{'ref': 'B200', 'amount': 200}, {'ref': 'D400', 'amount': 180}]\nUnmatched payments: [{'ref': 'F600', 'amount': 50}]\nMatched count: 4"

#### Explanation
- summary: The code matches invoice and payment pairs by reference and amount, removing matches from both unmatched lists using slicing that mutates the lists after each successful match. After the loop, only invoices B200 and D400 and payment F600 have no matches. Slicing unmatched_invoices[-2:] yields B200 and D400, and unmatched_payments[:2] yields just F600, as others have been removed. Four matches are made.
- principle: List slicing after each match mutates the unmatched lists, so slicing at the end operates on the already-mutated lists, not on the originals.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "Unmatched invoices: [{'ref': 'B200', 'amount': 200}, {'ref': 'D400', 'amount': 180}]\nUnmatched payments: [{'ref': 'F600', 'amount': 50}]\nMatched count: 4"; the verified output is authoritative regardless)
- why_wrong:
  - **c**: Misses that 4 matches are possible and doesn't track the mutation of the unmatched lists correctly, so includes two unmatched invoices/payments and only 3 matches.
  - **d**: Assumes slicing happens on the original, not the updated, unmatched lists, so two elements appear in each output list even after matches remove them.
  - **b**: Thinks unmatched_payments[:2] will always have 2 items, but after matching only one remains.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="Unmatched invoices: [{'ref': 'B200', 'amount': 200}, {'ref': 'D400', 'amount': 180}]\nUnmatched payments: [{'ref': 'F600', 'amount': 50}]\nMatched count: 4" expected_stdout="Unmatched invoices: [{'ref': 'B200', 'amount': 200}, {'ref': 'D400', 'amount': 180}]\nUnmatched payments: [{'ref': 'F600', 'amount': 50}]\nMatched count: 4"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `5663857a-9678-4396-8fba-2deaa8e0dc31` v1
status=in_review difficulty=7 concepts=['dict-mutation-during-iteration'] created_at=2026-07-12T02:25:13.312704+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def batch_vendor_payouts(vendor_payouts):
    processed = {}
    to_remove = []
    for vendor, amount in vendor_payouts.items():
        if amount == 0:
            to_remove.append(vendor)
            continue
        if amount < 0:
            # Negative payout, flag for manual review
            processed[vendor] = "manual_review"
            to_remove.append(vendor)
        elif amount < 100:
            # Minimum payout threshold not met, defer
            processed[vendor] = "deferred"
        else:
            processed[vendor] = "paid"
            vendor_payouts[vendor] -= 100
            if vendor_payouts[vendor] < 100:
                processed[vendor] += "+remaining"
    for vendor in to_remove:
        del vendor_payouts[vendor]
    return processed

def main():
    # Vendor payout balances as of today
    vendor_payouts = {
        "acme": 250,
        "globex": 90,
        "initech": -10,
        "soylent": 100,
        "umbrella": 0
    }
    result = batch_vendor_payouts(vendor_payouts)
    print(result)
    print(vendor_payouts)

main()
```
context: This batch payout routine processes accounts and updates the dict mid-iteration.

#### Question
What does this code print?
#### Choices
- **a**: {'acme': 'paid', 'globex': 'deferred', 'initech': 'manual_review', 'soylent': 'paid+remaining'}
{'acme': 150, 'globex': 90, 'soylent': 0} <-- correct
- **b**: {'acme': 'paid', 'globex': 'deferred', 'initech': 'manual_review', 'soylent': 'paid+remaining'}
{'acme': 150, 'globex': 90, 'soylent': 0, 'umbrella': 0}
- **c**: {'acme': 'paid', 'globex': 'deferred', 'initech': 'manual_review', 'soylent': 'paid+remaining', 'umbrella': 'manual_review'}
{'acme': 150, 'globex': 90, 'soylent': 100}
- **d**: {'acme': 'paid', 'globex': 'deferred', 'initech': 'manual_review', 'soylent': 'paid', 'umbrella': 'manual_review'}
{'acme': 150, 'globex': 90, 'soylent': 0}

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: "{'acme': 'paid', 'globex': 'deferred', 'initech': 'manual_review', 'soylent': 'paid+remaining'}\n{'acme': 150, 'globex': 90, 'soylent': 0}"

#### Explanation
- summary: The batch_vendor_payouts function iterates vendor_payouts and tracks vendors to remove in to_remove. 'umbrella' and 'initech' are removed due to zero or negative balances. 'acme' and 'soylent' are paid 100; 'acme' gets 'paid' (150 left), but 'soylent' falls below threshold and gets 'paid+remaining' (0 left). 'globex' is deferred. Only 'acme', 'globex', and 'soylent' remain in vendor_payouts since only nonzero, non-negative vendors are kept. Final print matches the actual output, with umbrella and initech removed from both dicts.
- principle: Mutation of a dictionary during iteration is safe only when collecting keys to remove and deleting them after iteration; in-place value mutation is allowed, but removing keys during iteration directly is not.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "{'acme': 'paid', 'globex': 'deferred', 'initech': 'manual_review', 'soylent': 'paid+remaining'}\n{'acme': 150, 'globex': 90, 'soylent': 0}"; the verified output is authoritative regardless)
- why_wrong:
  - **d**: Misses that after paying soylent 100, its remaining balance is now 0 (<100), so 'paid+remaining' is appended.
  - **c**: Incorrectly assumes vendor_payouts['soylent'] stays at 100 after payout, but the function decrements in place.
  - **b**: Forgets that umbrella is removed from vendor_payouts after the iteration because its payout is 0 and handled in the to_remove deletion pass.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="{'acme': 'paid', 'globex': 'deferred', 'initech': 'manual_review', 'soylent': 'paid+remaining'}\n{'acme': 150, 'globex': 90, 'soylent': 0}" expected_stdout="{'acme': 'paid', 'globex': 'deferred', 'initech': 'manual_review', 'soylent': 'paid+remaining'}\n{'acme': 150, 'globex': 90, 'soylent': 0}"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### spot_the_bug -- `1803aa12-10cd-47c2-8e6d-1efbf2f7362d` v1
status=in_review difficulty=7 concepts=['integer-division-truncation'] created_at=2026-07-12T02:26:00.746754+00:00
quality: defect_audit=flag solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: bug_lines_claim_mismatch, explanation_mismatch, defect_audit=flag

#### Code
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
context: Used in a batch job to calculate customer partial refunds for unused service periods.

#### Reason options
- **a**: The refund calculation truncates decimals instead of rounding to the nearest cent, resulting in underpayment for some customers. <-- correct
- **b**: The code fails to handle zero-day periods and would raise a ZeroDivisionError if total_days is 0.
- **c**: The code can return negative refunds if days_used exceeds total_days due to missing validation.
- **d**: The process_refunds function leaks exceptions and would terminate the batch if any record raises.

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [8, 9]
- correct_reason_id: a

#### Failing-test proof
```python
records = [{'order_total_cents': 1000, 'days_used': 7, 'total_days': 30}]
result = process_refunds(records)
print(repr(result))
assert result == [767], "Refund must be rounded to nearest cent, not truncated"
```

#### Explanation
- summary: The bug is that integer division (//) truncates the refund rather than rounding, causing refunds to be too low when the result is not an exact integer. This is especially visible for values that should round up, like when the fractional part is >= 0.5. The correct behavior is to round to the nearest cent, but the buggy code always rounds down.
- principle: When converting proportional values to integers for monetary amounts, use rounding instead of integer division to avoid systematic underpayment.
- mismatch_flagged: True (draft_explanation.line_notes ([7]) does not reference the sandbox-verified bug_lines ([8, 9]))

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 28, in <module>
AssertionError: Refund must be rounded to nearest cent, not truncated

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [8, 9] (diff-derived); generator claimed [7]
- [x] stb_claim_matches_execution -- buggy: claimed '[766]' executed '[766]'; fixed: claimed '[767]' executed '[767]'

#### Semantic gate verdicts
- **defect_audit**: flag -- defect_audit found zero defects on a has_bug=true candidate
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### trace -- `6bf398fe-ce6e-442a-ad96-fbac988a5cbc` v1
status=in_review difficulty=4 concepts=['off-by-one-slicing'] created_at=2026-07-12T02:26:39.606773+00:00
quality: solver=pass | solver_confidence=1.0 | clean

#### Code
```python
def base_shipping_rates():
    return [5, 10, 15, 20, 25]

def calculate_rates(weight_brackets, surcharge):
    # Only apply surcharge to all but the last bracket
    new_rates = weight_brackets[:-1]
    final_bracket = weight_brackets[-1]
    rates_with_surcharge = [r + surcharge for r in new_rates]
    rates_with_surcharge.append(final_bracket)
    return rates_with_surcharge

rates = base_shipping_rates()
# Remove first bracket and apply $3 surcharge to all except last
filtered_brackets = rates[1:]
final_rates = calculate_rates(filtered_brackets, 3)
print(final_rates)
```
context: A shipping module adjusts rates for all but the heaviest weight bracket.

#### Question
What does this code print?
#### Choices
- **a**: [13, 18, 23]
- **b**: [13, 18, 23, 25] <-- correct
- **c**: [10, 15, 20, 25]
- **d**: [8, 13, 18, 23, 25]

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: '[13, 18, 23, 25]'

#### Explanation
- summary: First, base_shipping_rates returns [5, 10, 15, 20, 25]. Slicing with rates[1:] removes the first element, yielding [10, 15, 20, 25]. In calculate_rates, weight_brackets[:-1] gives [10, 15, 20]; surcharge is added to each, resulting in [13, 18, 23]. The final element (25) is appended unchanged, so the answer is [13, 18, 23, 25].
- principle: Python list slicing is end-exclusive: x[:-1] excludes the last element, and x[1:] starts from the second element.
- mismatch_flagged: False
- why_wrong:
  - **d**: Assumes the surcharge is applied to every bracket, not realizing the last bracket is excluded from the surcharge and appended unchanged.
  - **c**: Ignores the initial removal of the first bracket (5), resulting in the original list minus one element instead of the correct transformation.
  - **a**: Thinks both the first and last elements are removed due to misunderstanding how slicing works, omitting the final bracket entirely.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='[13, 18, 23, 25]' expected_stdout='[13, 18, 23, 25]'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `17c52ad1-6f96-4715-a017-98c6d26daf7e` v1
status=in_review difficulty=10 concepts=['mutable-default-arg'] created_at=2026-07-12T02:27:49.077702+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
class LoyaltyLedger:
    def __init__(self):
        self._all_points = {}

    def award(self, user, amount, history=None):
        if history is None:
            history = []
        history.append((user, amount))
        self._all_points.setdefault(user, 0)
        self._all_points[user] += amount
        return history

    def revoke_last(self, history=None):
        if history is None:
            history = []
        if not history:
            return None
        user, amount = history.pop()
        self._all_points[user] -= amount
        return (user, amount)

    def user_points(self, user):
        return self._all_points.get(user, 0)

ledger = LoyaltyLedger()
hist_a = ledger.award('alice', 20)
hist_b = ledger.award('bob', 10)
hist_a2 = ledger.award('alice', 5, hist_a)
ledger.award('carol', 15)
ledger.revoke_last(hist_b)
ledger.award('alice', -3, hist_a2)
ledger.revoke_last()
ledger.award('bob', 25, hist_b)

print(hist_a)
print(hist_b)
print(ledger.user_points('alice'))
print(ledger.user_points('bob'))
print(ledger.user_points('carol'))
```
context: A loyalty program tracks and occasionally reverses points transactions per user.

#### Question
What does this code print?
#### Choices
- **a**: [('alice', 20), ('alice', 5), ('alice', -3)]
[('bob', 25)]
22
25
15 <-- correct
- **b**: [('alice', 20), ('alice', 5), ('alice', -3)]
[('bob', 25)]
22
10
15
- **c**: [('alice', 20), ('alice', 5), ('alice', -3)]
[('bob', 10)]
22
10
15
- **d**: [('alice', 20), ('alice', 5)]
[('bob', 25)]
25
25
15

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: "[('alice', 20), ('alice', 5), ('alice', -3)]\n[('bob', 25)]\n22\n25\n15"

#### Explanation
- summary: Each call to award or revoke_last with a supplied history list mutates that list in place due to explicit passing. Default arguments are avoided by always providing 'history', so no state is shared between unrelated users. hist_a is passed and mutated through hist_a2, so all alice transactions are recorded. hist_b is also mutated by award and revoke calls. Points are adjusted accordingly, and carol's points are not affected by revokes involving other histories.
- principle: Mutable objects (like lists) passed as arguments are mutated in place, and default mutable arguments can be dangerous if not handled with care.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "[('alice', 20), ('alice', 5), ('alice', -3)]\n[('bob', 25)]\n22\n25\n15"; the verified output is authoritative regardless)
- why_wrong:
  - **c**: Assumes each default argument gets a new list and that hist_b remains with a single entry; misses that hist_b is mutated in place and ignores the last revoke.
  - **b**: Assumes revoke_last(hist_b) undoes all bob's transactions (clears list) rather than just popping the last; so bob's points stay at 10 instead of 25.
  - **d**: Assumes passing hist_a2 to award does not mutate hist_a (i.e., that lists aren't aliased), so hist_a misses the -3 transaction and alice's total is not decreased.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="[('alice', 20), ('alice', 5), ('alice', -3)]\n[('bob', 25)]\n22\n25\n15" expected_stdout="[('alice', 20), ('alice', 5), ('alice', -3)]\n[('bob', 25)]\n22\n25\n15"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `d8541a90-4ced-446d-831c-d4d5336dd594` v1
status=in_review difficulty=10 concepts=['early-return-skipped-path'] created_at=2026-07-12T02:28:56.711402+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def recover_cart(user_carts, abandoned_users):
    # Try to recover cart for each abandoned user
    recovered = {}
    for user in abandoned_users:
        cart = user_carts.get(user)
        if not cart:
            continue  # Skip if no cart for user
        for item in cart:
            if item['qty'] == 0:
                break  # Can't recover if any item has qty 0
        else:
            recovered[user] = [item['sku'] for item in cart]
    return recovered

user_carts = {
    'alice': [
        {'sku': 'AA', 'qty': 1},
        {'sku': 'BB', 'qty': 2}
    ],
    'bob': [
        {'sku': 'CC', 'qty': 0},
        {'sku': 'DD', 'qty': 3}
    ],
    'carol': [
        {'sku': 'EE', 'qty': 4},
        {'sku': 'FF', 'qty': 5}
    ],
    'dave': []
}
abandoned_users = ['dave', 'bob', 'carol', 'alice']
# Let's simulate inventory updates before recovery:
user_carts['alice'][1]['qty'] = 0  # Alice's BB is now unavailable
user_carts['carol'][0]['qty'] = 0  # Carol's EE is now unavailable
user_carts['bob'][1]['qty'] = 1    # Bob's DD is restocked

result = recover_cart(user_carts, abandoned_users)
print(result)
```
context: A worker script tries to recover carts for users flagged as abandoned after some items have gone out of stock or been restocked, and prints the set of carts it could fully recover.

#### Question
What does this code print?
#### Choices
- **a**: {'carol': ['EE', 'FF']}
- **b**: {'bob': ['CC', 'DD'], 'carol': ['EE', 'FF']}
- **c**: {'alice': ['AA', 'BB']}
- **d**: {} <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: '{}'

#### Explanation
- summary: The function skips dave because his cart is empty. For bob, the cart has the first item (CC) with qty=0, so the break prevents recovering bob's cart. For carol, the first item (EE) has just been set to qty=0, so again break prevents recovery. For alice, the second item (BB) has qty=0 (updated just before), so break prevents recovery. Thus, none of the users get their carts recovered, and the result is the empty dict.
- principle: A for...else block only executes the else if the for loop is not exited via break; the break on any out-of-stock item prevents recovery for that user.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output '{}'; the verified output is authoritative regardless)
- why_wrong:
  - **a**: Assumes for...else runs if at least one item has qty>0, missing that break on any qty==0 skips else entirely for carol.
  - **c**: Ignores that alice's BB was updated to qty=0 before the function, so alice is not recovered.
  - **b**: Thinks break only skips the item, not the entire user's recovery logic; actually, any break prevents recovery of that user.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='{}' expected_stdout='{}'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### spot_the_bug -- `8ccfcfed-c436-4f1d-9030-0cfebaa47ce4` v1
status=in_review difficulty=5 concepts=['truthy-falsy-empty-check'] created_at=2026-07-12T03:16:58.246544+00:00
quality: defect_audit=flag solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: defect_audit=flag

#### Code
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
context: Resolves the retry limit for a route. Zero means the route is never retried.

#### Reason options
- **a**: dict.get() raises when the key is absent, so the default is never reached
- **b**: A configured value of 0 is falsy, so it is treated as absent and replaced by the default <-- correct
- **c**: format() coerces the limit to a string before the comparison happens
- **d**: The defaults dict is mutated by limit_for, so later calls see the override

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [7]
- correct_reason_id: b

#### Failing-test proof
```python
policy = RetryPolicy({"limit": 3})
result = policy.describe("/checkout", {"/checkout": 0})
print(repr(result))
assert result == "/checkout:0", "an explicit zero is honoured"

```

#### Explanation
- summary: A truthiness test cannot distinguish a configured 0 from a missing key, because both are falsy. A route explicitly set to zero retries therefore silently receives the default of three.
- principle: Test for absence with `is None`, not with truthiness, whenever 0, empty string, or empty collection is a legitimate value.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 16, in <module>
AssertionError: an explicit zero is honoured

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [7] (diff-derived); generator claimed [7]
- [x] stb_claim_matches_execution -- buggy: claimed "'/checkout:3'" executed "'/checkout:3'"; fixed: claimed "'/checkout:0'" executed "'/checkout:0'"

#### Semantic gate verdicts
- **defect_audit**: flag -- defect_audit found zero defects on a has_bug=true candidate
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `0434600e-b232-4e35-814e-ead0d323b49e` v1
status=in_review difficulty=5 concepts=['is-vs-equality'] created_at=2026-07-12T03:17:15.138132+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
```python
def find_matching_order(orders, target_id):
    for order in orders:
        if order["id"] is target_id:
            return order
    return None


def lookup_from_request(orders, raw_id):
    return find_matching_order(orders, int(raw_id))

```
context: Looks up an order by the identifier supplied in a request path.

#### Reason options
- **a**: int() raises on a string, so the lookup never runs
- **b**: An identity test compares object identity, and the parsed integer is a different object from the stored one <-- correct
- **c**: Dict subscripting returns a copy, so the comparison is against a temporary
- **d**: The loop returns on the first entry regardless of the comparison

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [3]
- correct_reason_id: b

#### Failing-test proof
```python
orders = [{"id": 1000, "total": 42}]
result = lookup_from_request(orders, "1000")
print(repr(result))
assert result == {"id": 1000, "total": 42}, "a parsed identifier matches by value"

```

#### Explanation
- summary: `is` asks whether two names refer to the same object, not whether they are equal. The identifier parsed from the request is a newly built integer, so it is a different object from the equal one stored in the order, and the lookup misses. It would appear to work for small identifiers, which CPython keeps interned.
- principle: Use `is` only for identity (None, sentinels). Use `==` to compare values.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 13, in <module>
AssertionError: a parsed identifier matches by value

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [3] (diff-derived); generator claimed [3]
- [x] stb_claim_matches_execution -- buggy: claimed 'None' executed 'None'; fixed: claimed "{'id': 1000, 'total': 42}" executed "{'id': 1000, 'total': 42}"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `778fd26c-3714-4ff1-9218-7804580ec519` v1
status=in_review difficulty=3 concepts=['truthy-falsy-empty-check'] created_at=2026-07-12T11:29:37.631244+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
```python
DEFAULT_SETTINGS = {
    "retries": 3,
    "timeout": 30,
    "verbose": True,
}


def resolve(overrides, key):
    value = overrides.get(key)
    if not value:
        return DEFAULT_SETTINGS[key]
    return value


def resolve_all(overrides):
    resolved = {}
    for key in DEFAULT_SETTINGS:
        resolved[key] = resolve(overrides, key)
    return resolved

```
context: Merges a caller's overrides onto the service defaults.

#### Reason options
- **a**: dict.get() raises KeyError when the key is absent, so the guard never runs
- **b**: 0 and False are falsy, so a value the caller supplied on purpose is discarded and replaced by the default <-- correct
- **c**: Iterating a dictionary yields its values, so resolve() receives the wrong argument
- **d**: DEFAULT_SETTINGS is mutated by resolve(), so later lookups see stale entries

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [10]
- correct_reason_id: b

#### Failing-test proof
```python
result = resolve_all({"retries": 0, "verbose": False})
print(repr(result))
assert result == {"retries": 0, "timeout": 30, "verbose": False}, "an explicit zero should survive"

```

#### Explanation
- summary: An override of 0 or False is a legitimate value, but both are falsy. Testing the value for truthiness cannot tell 'the caller said zero' apart from 'the caller said nothing', so a deliberate override is silently overwritten by the default.
- principle: To ask whether a value was supplied, compare against None. Truthiness answers a different question.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: an explicit zero should survive

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [10] (diff-derived); generator claimed [10]
- [x] stb_claim_matches_execution -- buggy: claimed "{'retries': 3, 'timeout': 30, 'verbose': True}" executed "{'retries': 3, 'timeout': 30, 'verbose': True}"; fixed: claimed "{'retries': 0, 'timeout': 30, 'verbose': False}" executed "{'retries': 0, 'timeout': 30, 'verbose': False}"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### predict_the_fix -- `21feb161-7469-4f66-b49a-7375c8090105` v1
status=in_review difficulty=3 concepts=['string-immutability-misuse'] created_at=2026-07-12T11:29:56.169809+00:00
quality: clean

#### Code
```python
def normalize_label(label):
    label.strip()
    label = label.lower()
    label = label.replace(" ", "-")
    return label


def normalize_all(labels):
    cleaned = []
    for label in labels:
        cleaned.append(normalize_label(label))
    return cleaned


def build_index(labels):
    index = {}
    for position, label in enumerate(normalize_all(labels)):
        index[label] = position
    return index

```
context: Turns human-typed category names into stable lookup keys.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def normalize_label(label):
    label.strip()
    label = label.lower()
    label = label.replace(" ", "-")
    if label.startswith("-"):
        label = label[1:]
    if label.endswith("-"):
        label = label[:-1]
    return label


def normalize_all(labels):
    cleaned = []
    for label in labels:
        cleaned.append(normalize_label(label))
    return cleaned


def build_index(labels):
    index = {}
    for position, label in enumerate(normalize_all(labels)):
        index[label] = position
    return index

- **b**: def normalize_label(label):
    label = label.lower()
    label.strip()
    label = label.replace(" ", "-")
    return label


def normalize_all(labels):
    cleaned = []
    for label in labels:
        cleaned.append(normalize_label(label))
    return cleaned


def build_index(labels):
    index = {}
    for position, label in enumerate(normalize_all(labels)):
        index[label] = position
    return index

- **c**: def normalize_label(label):
    label = label.lower()
    if label[0] == " ":
        label = label[1:]
    if label[-1] == " ":
        label = label[:-1]
    label = label.replace(" ", "-")
    return label


def normalize_all(labels):
    cleaned = []
    for label in labels:
        cleaned.append(normalize_label(label))
    return cleaned


def build_index(labels):
    index = {}
    for position, label in enumerate(normalize_all(labels)):
        index[label] = position
    return index

- **d**: def normalize_label(label):
    label = label.strip()
    label = label.lower()
    label = label.replace(" ", "-")
    return label


def normalize_all(labels):
    cleaned = []
    for label in labels:
        cleaned.append(normalize_label(label))
    return cleaned


def build_index(labels):
    index = {}
    for position, label in enumerate(normalize_all(labels)):
        index[label] = position
    return index
 <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: None

#### Explanation
- summary: Every string method returns a new string and leaves the original untouched. Calling strip() as a bare statement computes a trimmed copy and immediately discards it, so the padding survives into the following two steps.
- principle: String methods are pure. Their return value is the only thing that changed.
- mismatch_flagged: False
- why_wrong:
  - **a**: Attempts to trim hyphens caused by whitespace but neglects to strip the original whitespace, so extra hyphens may be removed but whitespace still present.
  - **b**: Moves lowercasing first but still forgets to assign the result of strip(), so whitespace is not removed.
  - **c**: Tries to remove only one leading and one trailing space instead of all, failing when there are multiple surrounding spaces.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: surrounding whitespace should be removed

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: surrounding whitespace should be removed

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 26, in <module>
AssertionError: surrounding whitespace should be removed

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: surrounding whitespace should be removed

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### spot_the_bug -- `5f6bee89-3387-4339-9c8e-781500dd6cc2` v1
status=in_review difficulty=3 concepts=['string-immutability-misuse'] created_at=2026-07-12T11:29:56.169809+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
```python
def normalize_label(label):
    label.strip()
    label = label.lower()
    label = label.replace(" ", "-")
    return label


def normalize_all(labels):
    cleaned = []
    for label in labels:
        cleaned.append(normalize_label(label))
    return cleaned


def build_index(labels):
    index = {}
    for position, label in enumerate(normalize_all(labels)):
        index[label] = position
    return index

```
context: Turns human-typed category names into stable lookup keys.

#### Reason options
- **a**: replace() only substitutes the first occurrence unless a count is given
- **b**: lower() rewrites the string in place, so the following call sees the original text
- **c**: enumerate() starts at 1, so every stored position is shifted by one
- **d**: Strings are immutable, so strip() hands back a new string and the result of that call is thrown away <-- correct

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [2]
- correct_reason_id: d

#### Failing-test proof
```python
result = build_index(["  Alpha One  "])
print(repr(result))
assert result == {"alpha-one": 0}, "surrounding whitespace should be removed"

```

#### Explanation
- summary: Every string method returns a new string and leaves the original untouched. Calling strip() as a bare statement computes a trimmed copy and immediately discards it, so the padding survives into the following two steps.
- principle: String methods are pure. Their return value is the only thing that changed.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: surrounding whitespace should be removed

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [2] (diff-derived); generator claimed [2]
- [x] stb_claim_matches_execution -- buggy: claimed "{'--alpha-one--': 0}" executed "{'--alpha-one--': 0}"; fixed: claimed "{'alpha-one': 0}" executed "{'alpha-one': 0}"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `64ead3a0-3682-4e8e-a73f-8451d33e56a9` v1
status=in_review difficulty=4 concepts=['float-precision'] created_at=2026-07-12T11:30:27.093684+00:00
quality: defect_audit=flag solver=pass reasons=pass | solver_confidence=1.0 | FLAGS: defect_audit=flag

#### Code
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
context: Checks a generated invoice against the total the customer was quoted.

#### Reason options
- **a**: A tuple cannot be unpacked in a for-loop, so amount is bound to the whole pair
- **b**: Binary floating point cannot hold these decimals exactly, so the accumulated sum is not bit-identical to the expected value <-- correct
- **c**: total is initialised to 0.0 rather than 0, which forces integer truncation
- **d**: line_total() is called twice, so the amount is doubled before the comparison

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [16]
- correct_reason_id: b

#### Failing-test proof
```python
result = audit(LINE_ITEMS, 0.3)["reconciles"]
print(repr(result))
assert result is True, "the line items should reconcile against the quoted total"

```

#### Explanation
- summary: 0.1 and 0.2 have no exact binary representation, so adding them yields 0.30000000000000004 rather than 0.3. Exact equality between two floats that were arrived at by different arithmetic almost never holds, even when the decimal maths agrees.
- principle: Compare floats within a tolerance chosen from the domain, never with equality.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 26, in <module>
AssertionError: the line items should reconcile against the quoted total

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [16] (diff-derived); generator claimed [16]
- [x] stb_claim_matches_execution -- buggy: claimed 'False' executed 'False'; fixed: claimed 'True' executed 'True'

#### Semantic gate verdicts
- **defect_audit**: flag -- defect_audit found zero defects on a has_bug=true candidate
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `bed3af5f-8e18-4893-bd9a-126ef560f718` v1
status=in_review difficulty=4 concepts=['is-vs-equality'] created_at=2026-07-12T11:30:45.032679+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Finds where a given row sits inside a freshly parsed table.

#### Reason options
- **a**: The identity operator asks whether two names point at the same object, and the parsed row is a different object from the target even though their contents match <-- correct
- **b**: enumerate() yields the value first and the index second, so position holds a list
- **c**: split(";") discards the final chunk, so the target row is never inspected
- **d**: Two lists cannot be compared with the equality operator, which would raise TypeError

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [3]
- correct_reason_id: a

#### Failing-test proof
```python
result = locate("1,2;3,4;5,6", [3, 4])["position"]
print(repr(result))
assert result == 1, "the matching row should be found by value"

```

#### Explanation
- summary: parse_rows() builds brand-new list objects. The caller's target is a separate object that merely holds the same numbers, so an identity test is False for every row and the search reports failure.
- principle: Identity asks 'the same object?'. Equality asks 'the same value?'. Data comparison almost always wants the second.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 23, in <module>
AssertionError: the matching row should be found by value

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [3] (diff-derived); generator claimed [3]
- [x] stb_claim_matches_execution -- buggy: claimed '-1' executed '-1'; fixed: claimed '1' executed '1'

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `4e41ec9e-fff9-445e-940c-b8fd4344e2b7` v1
status=in_review difficulty=4 concepts=['global-state-mutation'] created_at=2026-07-12T11:31:02.014219+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Layers a caller's settings on top of the service defaults before a run.

#### Reason options
- **a**: dict.update() returns a new dictionary, so the return value is discarded
- **b**: sorted() on a dictionary yields its values, so describe() reads the wrong side of each pair
- **c**: The second call passes an empty dictionary, so with_overrides() returns None
- **d**: The assignment binds a second name to the module-level dictionary rather than copying it, so every call permanently rewrites the shared defaults <-- correct

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [8]
- correct_reason_id: d

#### Failing-test proof
```python
result = run_twice({"retries": 9}, {})
print(repr(result))
assert result == "retries=3 timeout=30", "a later call should not inherit an earlier override"

```

#### Explanation
- summary: Assignment in Python binds a name; it does not copy. config and BASE_CONFIG therefore refer to one dictionary, and update() rewrites it in place. The first caller's override becomes the new default for everyone who follows.
- principle: Assignment binds, it does not copy. To leave a shared structure intact, copy it before mutating.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: a later call should not inherit an earlier override

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [8] (diff-derived); generator claimed [8]
- [x] stb_claim_matches_execution -- buggy: claimed "'retries=9 timeout=30'" executed "'retries=9 timeout=30'"; fixed: claimed "'retries=3 timeout=30'" executed "'retries=3 timeout=30'"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### predict_the_fix -- `e0a08ca9-1b0c-4d47-9e44-c9736eee40c8` v1
status=in_review difficulty=5 concepts=['dataclass-mutable-default'] created_at=2026-07-12T11:31:27.733007+00:00
quality: clean

#### Code
```python
import dataclasses


class Ledger:
    def __init__(self):
        self.entries = []

    def add(self, amount):
        self.entries.append(amount)

    def balance(self):
        return sum(self.entries)


@dataclasses.dataclass
class Account:
    owner: str
    ledger: Ledger = Ledger()


def open_accounts(owners):
    accounts = []
    for owner in owners:
        accounts.append(Account(owner))
    return accounts

```
context: Opens ledger-backed accounts for a batch of new customers.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: import dataclasses

class Ledger:
    def __init__(self):
        self.entries = []

    def add(self, amount):
        self.entries.append(amount)

    def balance(self):
        return sum(self.entries)

@dataclasses.dataclass
class Account:
    owner: str
    ledger: Ledger = Ledger()

    def __post_init__(self):
        if self.ledger is None:
            self.ledger = Ledger()

def open_accounts(owners):
    accounts = []
    for owner in owners:
        accounts.append(Account(owner))
    return accounts

- **b**: import dataclasses

class Ledger:
    def __init__(self):
        self.entries = []

    def add(self, amount):
        self.entries.append(amount)

    def balance(self):
        return sum(self.entries)

shared_ledger = Ledger()

@dataclasses.dataclass
class Account:
    owner: str
    ledger: Ledger = shared_ledger

def open_accounts(owners):
    accounts = []
    for owner in owners:
        accounts.append(Account(owner))
    return accounts

- **c**: import dataclasses


class Ledger:
    def __init__(self):
        self.entries = []

    def add(self, amount):
        self.entries.append(amount)

    def balance(self):
        return sum(self.entries)


@dataclasses.dataclass
class Account:
    owner: str
    ledger: Ledger = dataclasses.field(default_factory=Ledger)


def open_accounts(owners):
    accounts = []
    for owner in owners:
        accounts.append(Account(owner))
    return accounts
 <-- correct
- **d**: import dataclasses

class Ledger:
    def __init__(self):
        self.entries = []

    def add(self, amount):
        self.entries.append(amount)

    def balance(self):
        return sum(self.entries)

@dataclasses.dataclass
class Account:
    owner: str
    ledger: Ledger = Ledger()

    def reset_ledger(self):
        self.ledger = Ledger()

def open_accounts(owners):
    accounts = []
    for owner in owners:
        accounts.append(Account(owner))
    return accounts


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: None

#### Explanation
- summary: A dataclass field default is an ordinary expression, evaluated once while the class body runs. One Ledger is built at import time and handed to every Account that does not supply its own, so all accounts share a single balance.
- principle: A default value is created once, at definition time. For anything mutable, use default_factory so each instance gets its own.
- mismatch_flagged: False
- why_wrong:
  - **a**: Adds a __post_init__ that only creates a new Ledger if ledger is None, but since the default is Ledger(), this branch is never taken and the shared instance remains.
  - **b**: Moves the shared Ledger instance to a module-level variable, but this just makes the sharing explicit and does not fix the mutability issue.
  - **d**: Adds a method to reset the ledger but does not actually use it, so accounts still share the same Ledger instance.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 30, in <module>
AssertionError: a freshly opened account should start empty

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 30, in <module>
AssertionError: a freshly opened account should start empty

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 31, in <module>
AssertionError: a freshly opened account should start empty

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 29, in <module>
AssertionError: a freshly opened account should start empty

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### spot_the_bug -- `2fe2b7c2-3979-4088-9e4c-878f25826c77` v1
status=in_review difficulty=3 concepts=['off-by-one-slicing'] created_at=2026-07-12T11:31:47.695141+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Splits a result set into equal-size pages for the API response.

#### Reason options
- **a**: A slice already excludes its end index, so subtracting one more drops the last item of every page <-- correct
- **b**: divmod() hands back the remainder first, so page_count() is computed from the wrong half of the pair
- **c**: range() includes its upper bound, so one page too many is produced
- **d**: Slicing a list with a start index beyond its length raises IndexError

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [6]
- correct_reason_id: a

#### Failing-test proof
```python
result = paginate(["a", "b", "c", "d", "e", "f"])
print(repr(result))
assert result == [["a", "b", "c"], ["d", "e", "f"]], "every item should appear on exactly one page"

```

#### Explanation
- summary: A slice is already half-open: items[0:3] yields three items and stops before index 3. Subtracting one from the end index therefore takes PAGE_SIZE minus one items per page, and one record per page never reaches the caller.
- principle: Python slices exclude their upper bound. The end index is a stop, not a last index.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 24, in <module>
AssertionError: every item should appear on exactly one page

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [6] (diff-derived); generator claimed [6]
- [x] stb_claim_matches_execution -- buggy: claimed "[['a', 'b'], ['d', 'e']]" executed "[['a', 'b'], ['d', 'e']]"; fixed: claimed "[['a', 'b', 'c'], ['d', 'e', 'f']]" executed "[['a', 'b', 'c'], ['d', 'e', 'f']]"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `b3567247-a647-4269-a925-8789aab6338f` v1
status=in_review difficulty=4 concepts=['list-mutation-during-iteration'] created_at=2026-07-12T11:52:27.974167+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Cleans a batch of parsed spreadsheet rows before they are rendered.

#### Reason options
- **a**: The loop deletes from the very list it is walking, so everything after the deletion shifts down one place and the element that lands in the vacated index is never seen <-- correct
- **b**: remove() deletes every matching element, not just the first one
- **c**: continue skips the rest of the function, so kept is never appended to again
- **d**: An empty list is truthy, so the guard inside the loop never runs

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [5]
- correct_reason_id: a

#### Failing-test proof
```python
rows = [[1], [], [2], [3]]
result = report(rows)["kept"]
print(repr(result))
assert result == [[1], [2], [3]], "no populated row should be lost"

```

#### Explanation
- summary: The blank rows are already excluded by the continue, so nothing needs deleting. The deletion is pure damage: it shortens the list the for-loop is walking, every later element slides down one index, and the loop's counter marches straight past whatever landed in the gap.
- principle: Never delete from a sequence you are iterating. If you are building a new list anyway, you do not need to.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 27, in <module>
AssertionError: no populated row should be lost

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [5] (diff-derived); generator claimed [5]
- [x] stb_claim_matches_execution -- buggy: claimed '[[1], [3]]' executed '[[1], [3]]'; fixed: claimed '[[1], [2], [3]]' executed '[[1], [2], [3]]'

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `4f1eb607-79ea-409b-85ce-3a03fb690cbb` v1
status=in_review difficulty=4 concepts=['memoization-cache-staleness'] created_at=2026-07-12T11:53:45.482047+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Prices an item at several customer tiers. The cache exists because base lookups are expensive.

#### Reason options
- **a**: The cache key ignores the multiplier, so a result computed for one tier is served for every other tier <-- correct
- **b**: The cache is a module-level dictionary, and module-level state cannot persist between calls
- **c**: A list comprehension evaluates lazily, so every element ends up holding the last multiplier
- **d**: Membership testing with in scans the values of a dictionary, not its keys

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [5]
- correct_reason_id: a

#### Failing-test proof
```python
result = quote({"sku": "A1", "base": 10}, [1, 2])
print(repr(result))
assert result == [10, 20], "a different multiplier should be priced, not served from cache"

```

#### Explanation
- summary: A memo key must capture every input the result depends on. This one captures the item and forgets the multiplier, so the first tier priced wins forever and every subsequent tier is answered with a value computed for someone else.
- principle: The cache key must include every argument the cached value depends on. If it does not, the cache is a source of wrong answers.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 21, in <module>
AssertionError: a different multiplier should be priced, not served from cache

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [5] (diff-derived); generator claimed [5]
- [x] stb_claim_matches_execution -- buggy: claimed '[10, 10]' executed '[10, 10]'; fixed: claimed '[10, 20]' executed '[10, 20]'

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `8b2a18e6-54f2-4168-b86f-9ffa5374181f` v1
status=in_review difficulty=4 concepts=['encoding-decoding-mismatch'] created_at=2026-07-12T11:54:03.514748+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Carries text over a byte channel and reads it back on the far side.

#### Reason options
- **a**: The bytes are written in one encoding and read back in another, so a multi-byte character comes back as the several separate characters its bytes happen to spell <-- correct
- **b**: encode() and decode() are inverses regardless of the codec named, so the codec argument has no effect
- **c**: len() on a string returns its byte count, so the two sides can never agree
- **d**: A list comprehension cannot call a function that raises, so audit() silently returns an empty list

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [6]
- correct_reason_id: a

#### Failing-test proof
```python
result = audit(["caf\u00e9"])
print(repr(result))
assert result == [4], "a round trip should hand back what it was given"

```

#### Explanation
- summary: The writer spends two bytes on the accented character; the reader is told each byte is a whole character in a single-byte codec. Nothing raises. The text simply comes back one character longer than it went in, and the corruption travels quietly downstream.
- principle: The codec that reads must be the codec that wrote. A mismatch is silent, not fatal.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: a round trip should hand back what it was given

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [6] (diff-derived); generator claimed [6]
- [x] stb_claim_matches_execution -- buggy: claimed '[5]' executed '[5]'; fixed: claimed '[4]' executed '[4]'

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### predict_the_fix -- `e2ad0217-11bb-4dfe-87db-aa105c45920e` v1
status=in_review difficulty=3 concepts=['integer-division-truncation'] created_at=2026-07-12T11:54:25.728845+00:00
quality: clean

#### Code
```python
def mean(values):
    return sum(values) // len(values)


def spread(values):
    return max(values) - min(values)


def latency_report(values):
    if not values:
        return None
    return {
        "mean": mean(values),
        "spread": spread(values),
        "samples": len(values),
    }

```
context: Summarises a window of request latencies in milliseconds.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def mean(values):
    return sum(values) / len(values)


def spread(values):
    return max(values) - min(values)


def latency_report(values):
    if not values:
        return None
    return {
        "mean": mean(values),
        "spread": spread(values),
        "samples": len(values),
    }
 <-- correct
- **b**: def mean(values):
    return round(sum(values) // len(values), 2)


def spread(values):
    return max(values) - min(values)


def latency_report(values):
    if not values:
        return None
    return {
        "mean": mean(values),
        "spread": spread(values),
        "samples": len(values),
    }

- **c**: def mean(values):
    return float(sum(values) // len(values))


def spread(values):
    return max(values) - min(values)


def latency_report(values):
    if not values:
        return None
    return {
        "mean": mean(values),
        "spread": spread(values),
        "samples": len(values),
    }

- **d**: def mean(values):
    if len(values) == 0:
        return 0
    return sum(values) // len(values)


def spread(values):
    return max(values) - min(values)


def latency_report(values):
    if not values:
        return None
    return {
        "mean": mean(values),
        "spread": spread(values),
        "samples": len(values),
    }


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: None

#### Explanation
- summary: Two slashes is floor division: it discards the remainder and returns the whole part. Averaging ten and eleven gives ten and a half, and the report says ten. Every mean in the system is biased downward and nothing announces it.
- principle: Two slashes floors. One slash divides. Choose the one that matches the quantity you are reporting.
- mismatch_flagged: False
- why_wrong:
  - **b**: Rounds the integer-division result to two decimal places, but since integer division is used, it still returns a truncated mean.
  - **c**: Casts the integer result of integer division to float, so the mean is a float but still truncated, failing the test.
  - **d**: Adds a zero-length guard to mean, but still uses integer division, so truncated mean persists.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the mean of ten and eleven is ten and a half

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the mean of ten and eleven is ten and a half

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 21, in <module>
AssertionError: the mean of ten and eleven is ten and a half

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the mean of ten and eleven is ten and a half

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### spot_the_bug -- `3d0fd9e2-3c91-43a6-8e5c-7e4d2651a607` v1
status=in_review difficulty=3 concepts=['integer-division-truncation'] created_at=2026-07-12T11:54:25.728845+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
```python
def mean(values):
    return sum(values) // len(values)


def spread(values):
    return max(values) - min(values)


def latency_report(values):
    if not values:
        return None
    return {
        "mean": mean(values),
        "spread": spread(values),
        "samples": len(values),
    }

```
context: Summarises a window of request latencies in milliseconds.

#### Reason options
- **a**: The floor operator throws away the fractional part, so a mean that is not whole is reported low <-- correct
- **b**: sum() on a list of integers returns a float, so the division is already exact
- **c**: max() and min() are evaluated in the wrong order, so the spread comes back negative
- **d**: Dividing an integer by an integer in Python always truncates, whichever operator is used

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [2]
- correct_reason_id: a

#### Failing-test proof
```python
result = latency_report([10, 11])["mean"]
print(repr(result))
assert result == 10.5, "the mean of ten and eleven is ten and a half"

```

#### Explanation
- summary: Two slashes is floor division: it discards the remainder and returns the whole part. Averaging ten and eleven gives ten and a half, and the report says ten. Every mean in the system is biased downward and nothing announces it.
- principle: Two slashes floors. One slash divides. Choose the one that matches the quantity you are reporting.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the mean of ten and eleven is ten and a half

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [2] (diff-derived); generator claimed [2]
- [x] stb_claim_matches_execution -- buggy: claimed '10' executed '10'; fixed: claimed '10.5' executed '10.5'

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `6c542755-4a3d-4134-97d3-6dbe5b744707` v1
status=in_review difficulty=4 concepts=['closure-late-binding'] created_at=2026-07-12T11:54:42.540247+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Builds one transform per configured offset, then runs them all against a seed value.

#### Reason options
- **a**: Every lambda closes over the loop variable itself rather than its value at the time, so all of them read whatever it held when the loop finished <-- correct
- **b**: A lambda cannot refer to a name from the enclosing function, so offset is undefined when the step runs
- **c**: append() stores a copy of the lambda, so each step in the list is the same object
- **d**: The loop variable is deleted when the loop ends, so calling a step raises NameError

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [4]
- correct_reason_id: a

#### Failing-test proof
```python
result = run_pipeline([1, 10], 0)
print(repr(result))
assert result == [1, 10], "each step should carry the offset it was built with"

```

#### Explanation
- summary: A closure captures the variable, not a snapshot of it. All the lambdas share the single loop variable, and by the time any of them runs the loop has finished and left the last offset behind. Every step applies that one.
- principle: Closures capture names, not values. Bind the value at definition time, with a default argument or a factory.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: each step should carry the offset it was built with

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [4] (diff-derived); generator claimed [4]
- [x] stb_claim_matches_execution -- buggy: claimed '[10, 10]' executed '[10, 10]'; fixed: claimed '[1, 10]' executed '[1, 10]'

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `546ba9d6-124b-4c35-a478-b2e1ce713a19` v1
status=in_review difficulty=4 concepts=['shallow-vs-deep-copy'] created_at=2026-07-12T11:54:59.658039+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
```python
import copy

TEMPLATE = {
    "name": "unnamed",
    "tags": ["draft"],
}


def instantiate(template, name):
    made = copy.copy(template)
    made["name"] = name
    return made


def tag(record, label):
    record["tags"].append(label)
    return record

```
context: Stamps out records from a shared template, then lets callers tag them.

#### Reason options
- **a**: A shallow copy duplicates the outer dictionary but not the list inside it, so both records point at one list of tags <-- correct
- **b**: copy.copy() returns the original object unchanged, so instantiate() hands back the template itself
- **c**: Assigning to made["name"] rebinds the template's name as well, because strings are mutable
- **d**: append() returns a new list, so tag() discards its own result

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [10]
- correct_reason_id: a

#### Failing-test proof
```python
first = tag(instantiate(TEMPLATE, "alpha"), "urgent")
second = instantiate(TEMPLATE, "beta")
result = second["tags"]
print(repr(result))
assert result == ["draft"], "a fresh record should carry only the template tags"

```

#### Explanation
- summary: A shallow copy is one level deep. The new dictionary is genuinely new, so writing the name is safe, but every value inside it is the same object as before. The tags list is shared with the template, so tagging one record edits the template every later record is stamped from.
- principle: A shallow copy duplicates the container, not what it contains. For nested mutable structures, copy deeply.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: a fresh record should carry only the template tags

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [10] (diff-derived); generator claimed [10]
- [x] stb_claim_matches_execution -- buggy: claimed "['draft', 'urgent']" executed "['draft', 'urgent']"; fixed: claimed "['draft']" executed "['draft']"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### predict_the_fix -- `33635266-e3fe-4942-8f02-72c0e84784cc` v1
status=in_review difficulty=4 concepts=['shallow-vs-deep-copy'] created_at=2026-07-12T11:54:59.658039+00:00
quality: clean

#### Code
```python
import copy

TEMPLATE = {
    "name": "unnamed",
    "tags": ["draft"],
}


def instantiate(template, name):
    made = copy.copy(template)
    made["name"] = name
    return made


def tag(record, label):
    record["tags"].append(label)
    return record

```
context: Stamps out records from a shared template, then lets callers tag them.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: import copy

TEMPLATE = {
    "name": "unnamed",
    "tags": ["draft"],
}

def instantiate(template, name):
    made = copy.copy(template)
    if "tags" not in made:
        made["tags"] = ["draft"]
    made["name"] = name
    return made

def tag(record, label):
    record["tags"].append(label)
    return record

- **b**: import copy

TEMPLATE = {
    "name": "unnamed",
    "tags": ["draft"],
}

def instantiate(template, name):
    made = copy.copy(template)
    made["name"] = name
    made.setdefault("tags", ["draft"])
    return made

def tag(record, label):
    record["tags"].append(label)
    return record

- **c**: import copy

TEMPLATE = {
    "name": "unnamed",
    "tags": ["draft"],
}

def instantiate(template, name):
    made = copy.copy(template)
    made["name"] = str(name)
    return made

def tag(record, label):
    record["tags"].append(label)
    return record

- **d**: import copy

TEMPLATE = {
    "name": "unnamed",
    "tags": ["draft"],
}


def instantiate(template, name):
    made = copy.deepcopy(template)
    made["name"] = name
    return made


def tag(record, label):
    record["tags"].append(label)
    return record
 <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: None

#### Explanation
- summary: A shallow copy is one level deep. The new dictionary is genuinely new, so writing the name is safe, but every value inside it is the same object as before. The tags list is shared with the template, so tagging one record edits the template every later record is stamped from.
- principle: A shallow copy duplicates the container, not what it contains. For nested mutable structures, copy deeply.
- mismatch_flagged: False
- why_wrong:
  - **a**: It conditionally resets 'tags' only if missing, but since the shallow copy always has 'tags', it never creates a fresh list, so mutation persists.
  - **b**: It redundantly sets a default for 'tags', but since 'tags' is always present from the shallow copy, the underlying list is still shared and mutated.
  - **c**: It tries to ensure 'name' is a string, but does not address the shallow copy of the 'tags' list, so template mutation still leaks.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: a fresh record should carry only the template tags

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: a fresh record should carry only the template tags

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: a fresh record should carry only the template tags

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 21, in <module>
AssertionError: a fresh record should carry only the template tags

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### spot_the_bug -- `a1a8833a-7f39-4cd9-a526-9a844f3e2219` v1
status=in_review difficulty=4 concepts=['mutable-default-arg'] created_at=2026-07-12T11:55:21.459377+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Collects the timing of each step of a request, so the slowest can be reported.

#### Reason options
- **a**: The empty dictionary is built once, when the function is defined, so every request that does not pass one appends to the same shared object <-- correct
- **b**: A dictionary cannot be used as a default argument, so Python rebuilds it on every call
- **c**: sorted() on items() yields keys only, so slowest() ranks the span names
- **d**: Assigning spans inside the loop rebinds the caller's name, so only the last step survives

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [1]
- correct_reason_id: a

#### Failing-test proof
```python
handle("warmup", 99)
result = handle("db", 5)["spans"]
print(repr(result))
assert result == {"db": 5}, "a new request should start with no spans"

```

#### Explanation
- summary: A default argument is evaluated once, when the def statement runs. The dictionary therefore belongs to the function, not to the call, and every request that omits it writes into the same object. Yesterday's spans turn up in today's trace.
- principle: Default arguments are evaluated at definition time. Never default to a mutable object.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: a new request should start with no spans

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [1] (diff-derived); generator claimed [1]
- [x] stb_claim_matches_execution -- buggy: claimed "{'warmup': 99, 'db': 5}" executed "{'warmup': 99, 'db': 5}"; fixed: claimed "{'db': 5}" executed "{'db': 5}"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `2e4c2d75-4ee3-4b3e-8ce2-4713c00e99f7` v1
status=in_review difficulty=3 concepts=['off-by-one'] created_at=2026-07-12T11:55:39.355710+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
```python
def window_days(first, last):
    days = []
    for day in range(first, last):
        days.append(day)
    return days


def retained(events, first, last):
    days = window_days(first, last)
    kept = []
    for event in events:
        if event["day"] in days:
            kept.append(event["id"])
    return kept


def summary(events, first, last):
    return {"kept": retained(events, first, last), "span": len(window_days(first, last))}

```
context: Selects the events that fall inside an inclusive retention window, first day to last day.

#### Reason options
- **a**: range() stops before its second argument, so the last day of an inclusive window is never in the list <-- correct
- **b**: range() starts at zero regardless of its first argument, so the window is shifted
- **c**: Membership testing with in on a list raises TypeError when the list holds integers
- **d**: append() inside the loop overwrites the previous entry, so days only ever holds one value

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [3]
- correct_reason_id: a

#### Failing-test proof
```python
events = [{"id": "a", "day": 1}, {"id": "b", "day": 3}]
result = summary(events, 1, 3)["kept"]
print(repr(result))
assert result == ["a", "b"], "a window from day one to day three includes day three"

```

#### Explanation
- summary: The window is documented as inclusive of both ends, but range() stops one short of its upper argument. The final day is quietly outside the window, so every event on the last day of every window is dropped.
- principle: range(a, b) stops before b. An inclusive upper bound needs b plus one.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: a window from day one to day three includes day three

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [3] (diff-derived); generator claimed [3]
- [x] stb_claim_matches_execution -- buggy: claimed "['a']" executed "['a']"; fixed: claimed "['a', 'b']" executed "['a', 'b']"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### predict_the_fix -- `0774a668-33fd-4c01-a1b3-8636359f0c12` v1
status=in_review difficulty=3 concepts=['off-by-one'] created_at=2026-07-12T11:55:39.355710+00:00
quality: clean

#### Code
```python
def window_days(first, last):
    days = []
    for day in range(first, last):
        days.append(day)
    return days


def retained(events, first, last):
    days = window_days(first, last)
    kept = []
    for event in events:
        if event["day"] in days:
            kept.append(event["id"])
    return kept


def summary(events, first, last):
    return {"kept": retained(events, first, last), "span": len(window_days(first, last))}

```
context: Selects the events that fall inside an inclusive retention window, first day to last day.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def window_days(first, last):
    days = []
    for day in range(first, last + 1):
        days.append(day)
    return days


def retained(events, first, last):
    days = window_days(first, last)
    kept = []
    for event in events:
        if event["day"] in days:
            kept.append(event["id"])
    return kept


def summary(events, first, last):
    return {"kept": retained(events, first, last), "span": len(window_days(first, last))}
 <-- correct
- **b**: def window_days(first, last):
    days = []
    for day in range(first, last):
        days.append(day)
    if last == first:
        days.append(last)
    return days


def retained(events, first, last):
    days = window_days(first, last)
    kept = []
    for event in events:
        if event["day"] in days:
            kept.append(event["id"])
    return kept


def summary(events, first, last):
    return {"kept": retained(events, first, last), "span": len(window_days(first, last))}

- **c**: def window_days(first, last):
    days = []
    if first != last:
        for day in range(first, last):
            days.append(day)
    else:
        days.append(first)
    return days


def retained(events, first, last):
    days = window_days(first, last)
    kept = []
    for event in events:
        if event["day"] in days:
            kept.append(event["id"])
    return kept


def summary(events, first, last):
    return {"kept": retained(events, first, last), "span": len(window_days(first, last))}

- **d**: def window_days(first, last):
    days = []
    for day in range(first, last):
        days.append(day)
    if last > first:
        days.append(last - 1)
    return days


def retained(events, first, last):
    days = window_days(first, last)
    kept = []
    for event in events:
        if event["day"] in days:
            kept.append(event["id"])
    return kept


def summary(events, first, last):
    return {"kept": retained(events, first, last), "span": len(window_days(first, last))}


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: None

#### Explanation
- summary: The window is documented as inclusive of both ends, but range() stops one short of its upper argument. The final day is quietly outside the window, so every event on the last day of every window is dropped.
- principle: range(a, b) stops before b. An inclusive upper bound needs b plus one.
- mismatch_flagged: False
- why_wrong:
  - **b**: Handles the degenerate case where first == last but does not fix the range for first < last, so the last day is still omitted.
  - **c**: Special-cases when first == last, but does not include the last day for windows where first < last, so the test still fails.
  - **d**: Attempts to fix by appending last-1, which is already included by range, so last is still not included, and the test still fails.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: a window from day one to day three includes day three

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: a window from day one to day three includes day three

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 24, in <module>
AssertionError: a window from day one to day three includes day three

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 24, in <module>
AssertionError: a window from day one to day three includes day three

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### spot_the_bug -- `5876c089-5e1a-4988-a490-264964a2bde6` v1
status=in_review difficulty=4 concepts=['string-vs-bytes-confusion'] created_at=2026-07-12T12:07:10.509226+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Prepares labels for a binary record format that budgets ten bytes per field.

#### Reason options
- **a**: The length is taken from the unencoded string, so a character that costs more than one byte in UTF-8 slips past a budget that is measured in bytes <-- correct
- **b**: encode() rewrites the string in place, so len() already sees the encoded form
- **c**: UTF-8 spends exactly two bytes on every character, so the count is always double what len() reports
- **d**: packed is rebuilt on each pass of the loop, so only the last record is ever returned

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [6]
- correct_reason_id: a

#### Failing-test proof
```python
result = pack([{"label": "caf\u00e9-latte"}])[0]
print(repr(result))
assert result is None, "the label overruns a ten-byte field"

```

#### Explanation
- summary: The line above produces the bytes that will actually be written, but the guard measures the string those bytes came from. A str counts characters; the field counts bytes. UTF-8 spends one byte on ASCII and two or more on anything else, so an over-long label sails through the check and is silently written past the end of its field.
- principle: Measure the thing you are about to store, in the unit the destination counts.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the label overruns a ten-byte field

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [6] (diff-derived); generator claimed [6]
- [x] stb_claim_matches_execution -- buggy: claimed "b'caf\\xc3\\xa9-latte'" executed "b'caf\\xc3\\xa9-latte'"; fixed: claimed 'None' executed 'None'

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `20c12e7a-9a8a-4070-ba31-25b1be99da8e` v1
status=in_review difficulty=4 concepts=['injection-string-concat'] created_at=2026-07-12T12:07:42.956819+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
```python
def quote(value):
    return value.replace("'", "''")


def build_query(table, name):
    return "SELECT * FROM " + table + " WHERE name = '" + name + "'"


def build_all(table, names):
    queries = []
    for name in names:
        queries.append(build_query(table, name))
    return queries


def describe(queries):
    return {"queries": queries, "count": len(queries)}

```
context: Builds the read-only report queries that a downstream tool executes.

#### Reason options
- **a**: The caller value is pasted straight between the quotes, so a value containing a quote character closes the literal early and the rest is read as query text <-- correct
- **b**: quote() is applied to the table name but not to the caller value, which is why only one of the two is safe
- **c**: The table name is interpolated the same way, and that is the only untrusted part of the query
- **d**: replace() substitutes only the first occurrence, so quote() would not help even if it were called

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [6]
- correct_reason_id: a

#### Failing-test proof
```python
result = describe(build_all("users", ["O'Brien"]))["queries"][0]
print(repr(result))
assert result == "SELECT * FROM users WHERE name = 'O''Brien'", "the caller value must be quoted"

```

#### Explanation
- summary: quote() exists and is never called. The caller's value is concatenated straight into the literal, so a single quote inside it terminates the literal and everything after it is parsed as part of the statement. The helper right above shows what should have happened to it.
- principle: Never concatenate an untrusted value into a query. Bind it, or at minimum escape it.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: the caller value must be quoted

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [6] (diff-derived); generator claimed [6]
- [x] stb_claim_matches_execution -- buggy: claimed '"SELECT * FROM users WHERE name = \'O\'Brien\'"' executed '"SELECT * FROM users WHERE name = \'O\'Brien\'"'; fixed: claimed '"SELECT * FROM users WHERE name = \'O\'\'Brien\'"' executed '"SELECT * FROM users WHERE name = \'O\'\'Brien\'"'

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### predict_the_fix -- `b8141641-db53-4982-a5bf-1386bac144a6` v1
status=in_review difficulty=4 concepts=['injection-string-concat'] created_at=2026-07-12T12:07:42.956819+00:00
quality: clean

#### Code
```python
def quote(value):
    return value.replace("'", "''")


def build_query(table, name):
    return "SELECT * FROM " + table + " WHERE name = '" + name + "'"


def build_all(table, names):
    queries = []
    for name in names:
        queries.append(build_query(table, name))
    return queries


def describe(queries):
    return {"queries": queries, "count": len(queries)}

```
context: Builds the read-only report queries that a downstream tool executes.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def quote(value):
    return value.replace("'", "''")


def build_query(table, name):
    return "SELECT * FROM " + table + " WHERE name = '" + name.strip() + "'"


def build_all(table, names):
    queries = []
    for name in names:
        queries.append(build_query(table, name))
    return queries


def describe(queries):
    return {"queries": queries, "count": len(queries)}

- **b**: def quote(value):
    return value.replace("'", "''")


def build_query(table, name):
    return "SELECT * FROM " + table + " WHERE name = '" + quote(name) + "'"


def build_all(table, names):
    queries = []
    for name in names:
        queries.append(build_query(table, name))
    return queries


def describe(queries):
    return {"queries": queries, "count": len(queries)}
 <-- correct
- **c**: def quote(value):
    return value.replace("'", "''")


def build_query(table, name):
    return ("SELECT * FROM " + table + " WHERE name = '" + name + "'").replace(";", "")


def build_all(table, names):
    queries = []
    for name in names:
        queries.append(build_query(table, name))
    return queries


def describe(queries):
    return {"queries": queries, "count": len(queries)}

- **d**: def quote(value):
    return value.replace("'", "''")


def build_query(table, name):
    if "'" in name:
        name = name.replace("'", " ")
    return "SELECT * FROM " + table + " WHERE name = '" + name + "'"


def build_all(table, names):
    queries = []
    for name in names:
        queries.append(build_query(table, name))
    return queries


def describe(queries):
    return {"queries": queries, "count": len(queries)}


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: None

#### Explanation
- summary: quote() exists and is never called. The caller's value is concatenated straight into the literal, so a single quote inside it terminates the literal and everything after it is parsed as part of the statement. The helper right above shows what should have happened to it.
- principle: Never concatenate an untrusted value into a query. Bind it, or at minimum escape it.
- mismatch_flagged: False
- why_wrong:
  - **a**: It trims whitespace from the name, which may seem like sanitization, but does not escape single quotes so the injection bug remains.
  - **c**: It attempts to prevent injection by removing semicolons from the final query string, but does not address dangerous single quotes in name.
  - **d**: It replaces single quotes with spaces instead of escaping them, altering the data rather than safely quoting it, so the query is still wrong.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: the caller value must be quoted

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: the caller value must be quoted

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: the caller value must be quoted

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: the caller value must be quoted

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `5207abba-151d-4d33-b3da-9343891beda6` v1
status=in_review difficulty=4 concepts=['aliasing-vs-copy'] created_at=2026-07-12T12:08:01.900268+00:00
quality: clean

#### Code
```python
def describe(rows):
    if not rows:
        return {"count": 0, "last": None}
    return {"count": len(rows), "last": rows[-1]}


def audit(rows, extra):
    before = rows
    rows.append(extra)
    return {
        "before": before,
        "after": rows,
        "summary": describe(rows),
    }
def run(rows, extra):
    return audit(rows, extra)["before"]

```
context: Records what a list held before a row was added, so the two states can be compared.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def describe(rows):
    if not rows:
        return {"count": 0, "last": None}
    return {"count": len(rows), "last": rows[-1]}


def audit(rows, extra):
    before = rows
    after = rows + [extra]
    rows.append(extra)
    return {
        "before": before,
        "after": after,
        "summary": describe(after),
    }
def run(rows, extra):
    return audit(rows, extra)["before"]

- **b**: def describe(rows):
    if not rows:
        return {"count": 0, "last": None}
    return {"count": len(rows), "last": rows[-1]}


def audit(rows, extra):
    before = rows[:]
    rows.append(extra)
    return {
        "before": rows,
        "after": rows,
        "summary": describe(rows),
    }
def run(rows, extra):
    return audit(rows, extra)["before"]

- **c**: def describe(rows):
    if not rows:
        return {"count": 0, "last": None}
    return {"count": len(rows), "last": rows[-1]}


def audit(rows, extra):
    before = list(rows)
    rows.append(extra)
    return {
        "before": before,
        "after": rows,
        "summary": describe(rows),
    }
def run(rows, extra):
    return audit(rows, extra)["before"]
 <-- correct
- **d**: def describe(rows):
    if not rows:
        return {"count": 0, "last": None}
    return {"count": len(rows), "last": rows[-1]}


def audit(rows, extra):
    before = rows.copy()
    rows.append(extra)
    return {
        "before": rows,
        "after": rows,
        "summary": describe(rows),
    }
def run(rows, extra):
    return audit(rows, extra)["before"]


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: None

#### Explanation
- summary: Assignment binds a name; it does not copy. before and rows are two names for one list, so the row appended on the very next line is visible through both. The record of what came before shows something that came after.
- principle: Assignment shares. To capture a mutable value at a moment in time, copy it.
- mismatch_flagged: False
- why_wrong:
  - **a**: Builds 'after' using list concatenation but still sets 'before' to the original (aliased) list, so 'before' reflects the appended value.
  - **b**: Uses slicing to create a copy for 'before', but then still returns 'rows' (the mutated list) as 'before', so the aliasing issue remains.
  - **d**: Attempts to use copy() but assigns 'before' correctly and then overwrites it by returning 'rows', so 'before' still reflects the mutated list.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the record of what came before should not show the later row

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the record of what came before should not show the later row

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the record of what came before should not show the later row

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: the record of what came before should not show the later row

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### spot_the_bug -- `4a6ae494-205c-4dca-b97d-c631dee08e50` v1
status=in_review difficulty=4 concepts=['aliasing-vs-copy'] created_at=2026-07-12T12:08:01.900268+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
```python
def describe(rows):
    if not rows:
        return {"count": 0, "last": None}
    return {"count": len(rows), "last": rows[-1]}


def audit(rows, extra):
    before = rows
    rows.append(extra)
    return {
        "before": before,
        "after": rows,
        "summary": describe(rows),
    }
def run(rows, extra):
    return audit(rows, extra)["before"]

```
context: Records what a list held before a row was added, so the two states can be compared.

#### Reason options
- **a**: Binding a second name to a list does not copy it, so before and rows are one object and the appended row shows up in both <-- correct
- **b**: append() returns a new list, so the append mutates a temporary and rows is left untouched
- **c**: Building a dictionary copies each value into it, so before is already independent by the time audit returns
- **d**: rows[-1] raises IndexError on a list with a single element, so describe cannot be trusted

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [8]
- correct_reason_id: a

#### Failing-test proof
```python
result = run(["a", "b"], "late")
print(repr(result))
assert result == ["a", "b"], "the record of what came before should not show the later row"

```

#### Explanation
- summary: Assignment binds a name; it does not copy. before and rows are two names for one list, so the row appended on the very next line is visible through both. The record of what came before shows something that came after.
- principle: Assignment shares. To capture a mutable value at a moment in time, copy it.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the record of what came before should not show the later row

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [8] (diff-derived); generator claimed [8]
- [x] stb_claim_matches_execution -- buggy: claimed "['a', 'b', 'late']" executed "['a', 'b', 'late']"; fixed: claimed "['a', 'b']" executed "['a', 'b']"

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### spot_the_bug -- `f4fb97c6-3d86-40e3-bb49-77fd8c00e0cf` v1
status=in_review difficulty=4 concepts=['timezone-naive-vs-aware'] created_at=2026-07-12T12:08:18.973772+00:00
quality: defect_audit=pass solver=pass reasons=pass | solver_confidence=1.0 | clean

#### Code
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
context: Reports how many minutes each job has left, given a start in the operator's zone and a deadline in UTC.

#### Reason options
- **a**: Replacing the zone relabels the wall-clock reading as UTC instead of converting it, so the instant silently moves by the size of the offset <-- correct
- **b**: Two aware datetimes cannot be subtracted, so the subtraction raises TypeError
- **c**: total_seconds() already returns whole minutes, so the floor division divides by sixty a second time
- **d**: datetime.timezone.utc is a naive zone, so every value built from it is naive

#### Verified answer key (sandbox-derived, D-49)
- correct_lines: [7]
- correct_reason_id: a

#### Failing-test proof
```python
east = datetime.timezone(datetime.timedelta(hours=5))
jobs = [{"start": datetime.datetime(2026, 1, 1, 12, 0, tzinfo=east)}]
deadline = datetime.datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
result = schedule(jobs, deadline)
print(repr(result))
assert result == [60], "noon in a plus-five zone is 07:00 UTC, one hour before the deadline"

```

#### Explanation
- summary: replace() edits the label on the reading and leaves the digits alone: noon in a plus-five zone becomes noon UTC, an instant five hours earlier than the operator meant. astimezone() moves the digits so the instant survives the conversion.
- principle: replace(tzinfo=...) relabels. astimezone() converts. Only one of them preserves the instant.
- mismatch_flagged: False

#### Sandbox checks
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: noon in a plus-five zone is 07:00 UTC, one hour before the deadline

- [x] fixed_passes_test
- [x] buggy_runs_clean
- [x] deterministic_double_run
- [x] fix_diff_real_and_minimal -- verified bug_lines [7] (diff-derived); generator claimed [7]
- [x] stb_claim_matches_execution -- buggy: claimed '[-240]' executed '[-240]'; fixed: claimed '[60]' executed '[60]'

#### Semantic gate verdicts
- **defect_audit**: pass -- exactly one defect, overlapping the verified bug region
- **solver**: pass -- solver matched the answer key
- **reasons**: pass -- exactly one correct option, matching the key

---

### trace -- `13d21d87-a378-4aa0-ae32-c807026e0d1d` v1
status=in_review difficulty=7 concepts=['string-formatting-mismatch'] created_at=2026-07-12T12:20:00.847496+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def rank_recommendations(scores, products):
    # Pair each product with its score
    paired = list(zip(products, scores))
    # Sort by score descending
    paired.sort(key=lambda x: x[1], reverse=True)
    # Format the output strings
    lines = []
    for idx, (product, score) in enumerate(paired, 1):
        # Intentionally mismatched formatting: expecting int, gets float
        try:
            lines.append("{}. {} (score: {:d})".format(idx, product, score))
        except ValueError as e:
            lines.append(f"Error formatting {product}: {e.__class__.__name__}")
    return lines

# Production usage: these scores come from a model
scores = [8.9, 10.0, 8.0]
products = ["Toaster", "Blender", "Microwave"]

for line in rank_recommendations(scores, products):
    print(line)
```
context: In a recommendation engine, formatting a ranked product list for display.

#### Question
What does this code print?
#### Choices
- **a**: Error formatting Blender: ValueError
Error formatting Toaster: ValueError
Error formatting Microwave: ValueError <-- correct
- **b**: 1. Blender (score: 10)
2. Toaster (score: 8.9)
3. Microwave (score: Error formatting Microwave: ValueError)
- **c**: 1. Blender (score: 10.0)
2. Toaster (score: 8.9)
3. Microwave (score: 8.0)
- **d**: 1. Blender (score: 10)
2. Toaster (score: Error formatting Toaster: ValueError)
3. Microwave (score: Error formatting Microwave: ValueError)

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: 'Error formatting Blender: ValueError\nError formatting Toaster: ValueError\nError formatting Microwave: ValueError'

#### Explanation
- summary: The code pairs products and scores, sorts them by score descending, and attempts to format each as an integer in the output string. But using '{:d}' with any float (even 10.0) raises ValueError; the code catches this and prints an error for each product.
- principle: The {:d} format code expects an integer; passing any float (even 10.0) to it raises ValueError.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output 'Error formatting Blender: ValueError\nError formatting Toaster: ValueError\nError formatting Microwave: ValueError'; the verified output is authoritative regardless)
- why_wrong:
  - **d**: This assumes {:d} will accept 10.0, but {:d} rejects all floats (even those whose value is integral), so all lines produce error messages.
  - **c**: This assumes the format code accepts any type or defaults to string, but {:d} only works for ints; floats always raise.
  - **b**: This assumes {:d} only fails if the float has a fractional part, but any float (even 8.0) fails with ValueError.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='Error formatting Blender: ValueError\nError formatting Toaster: ValueError\nError formatting Microwave: ValueError' expected_stdout='Error formatting Blender: ValueError\nError formatting Toaster: ValueError\nError formatting Microwave: ValueError'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `87e4d8b2-7507-4ce8-819b-eb232d049f75` v1
status=in_review difficulty=1 concepts=['string-formatting-mismatch'] created_at=2026-07-12T12:21:38.271278+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
MAX_REQUESTS = 100
window_seconds = 60
usage = 87

rate = usage / window_seconds
remaining = MAX_REQUESTS - usage

print(f"Current rate: {rate:.2f} req/s")
print(f"Remaining: {remaining}")

# Show next available time if rate would be exceeded
if usage >= MAX_REQUESTS:
    next_time = window_seconds * ((usage // MAX_REQUESTS) + 1)
    print(f"Next window resets in {next_time}s")
```
context: Code displays current rate limits and remaining quota for an API.

#### Question
What does this code print?
#### Choices
- **a**: Current rate: 1.45 req/s
Remaining: 13 <-- correct
- **b**: Current rate: 1.45 req/s
Remaining: 13
Next window resets in 120s
- **c**: Current rate: 1.0 req/s
Remaining: 13
- **d**: Current rate: 1.45 req/s
Remaining: 100

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: 'Current rate: 1.45 req/s\nRemaining: 13'

#### Explanation
- summary: Variables are first set with MAX_REQUESTS = 100, window_seconds = 60, and usage = 87. The rate is calculated as 87 / 60 = 1.45 (formatted to 2 decimals). Remaining is 100 - 87 = 13. The conditional checking if usage >= MAX_REQUESTS is false (since 87 < 100), so the block for 'Next window resets...' is skipped.
- principle: String formatting with f-strings prints the floating point division result to two decimals; the conditional block only prints if its guard condition is met.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output 'Current rate: 1.45 req/s\nRemaining: 13'; the verified output is authoritative regardless)
- why_wrong:
  - **c**: Used integer division in rate calculation, yielding 1 instead of 1.45.
  - **b**: Assumed the 'next window resets' line always prints, but the conditional was false.
  - **d**: Mistook the remaining quota as unchanged or reset, not decremented by usage.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='Current rate: 1.45 req/s\nRemaining: 13' expected_stdout='Current rate: 1.45 req/s\nRemaining: 13'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `f5045866-9a31-4a5d-9306-16db39c62c04` v1
status=in_review difficulty=5 concepts=['truthy-falsy-empty-check'] created_at=2026-07-12T12:22:21.221014+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def choose_welcome_message(user):
    if not user.get("email_verified"):
        if not user.get("email"):
            return "Please provide your email."
        else:
            return f"Verify your email: {user['email']}"
    if user.get("profile"):
        profile = user["profile"]
        if profile.get("first_name") and profile.get("last_name"):
            return f"Welcome, {profile['first_name']} {profile['last_name']}!"
        elif profile.get("first_name"):
            return f"Welcome, {profile['first_name']}!"
    return "Welcome!"

users = [
    {"email": "tina@example.com", "email_verified": False},
    {"email": "sanjay@example.com", "email_verified": True, "profile": {"first_name": "Sanjay"}},
    {"email": "li@example.com", "email_verified": True, "profile": {"first_name": "Li", "last_name": "Zhang"}},
    {"email_verified": False},
    {"email": "chris@example.com", "email_verified": True}
]

for user in users:
    print(choose_welcome_message(user))
```
context: In a user onboarding flow, different welcome messages depend on profile and email state.

#### Question
What does this code print?
#### Choices
- **a**: Verify your email: tina@example.com
Welcome, Sanjay!
Welcome, Li Zhang!
Please provide your email.
Welcome, Chris!
- **b**: Verify your email: tina@example.com
Welcome, Sanjay!
Welcome, Li Zhang!
Please provide your email.
Welcome! <-- correct
- **c**: Verify your email: tina@example.com
Welcome, Sanjay!
Welcome, Li Zhang!
Please provide your email.
Welcome, chris@example.com!
- **d**: Verify your email: tina@example.com
Welcome, Sanjay!
Verify your email: li@example.com
Please provide your email.
Welcome, chris@example.com!

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: 'Verify your email: tina@example.com\nWelcome, Sanjay!\nWelcome, Li Zhang!\nPlease provide your email.\nWelcome!'

#### Explanation
- summary: For each user, choose_welcome_message is called. For user 1, email_verified is False and email is present, so 'Verify your email...' is returned. For user 2, email_verified is True and first_name is present in the profile, so 'Welcome, Sanjay!' is printed. User 3 has both first_name and last_name, so the full name is used. User 4 has no email, so 'Please provide your email.' is printed. User 5 has no profile, so the generic 'Welcome!' is printed.
- principle: In Python, empty containers (dicts, lists, strings) are falsy, so checks like 'if not user.get("email")' distinguish between missing/empty values and those that are present and nonempty.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output 'Verify your email: tina@example.com\nWelcome, Sanjay!\nWelcome, Li Zhang!\nPlease provide your email.\nWelcome!'; the verified output is authoritative regardless)
- why_wrong:
  - **c**: Assumes having an email means you get a personalized welcome, but the code only uses email for verification and profile for names.
  - **a**: Invents extracting first_name from the email, which the code never does.
  - **d**: Thinks the 'Verify' path runs for any user with an email, missing the True check on email_verified, and misapplies that to later users.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='Verify your email: tina@example.com\nWelcome, Sanjay!\nWelcome, Li Zhang!\nPlease provide your email.\nWelcome!' expected_stdout='Verify your email: tina@example.com\nWelcome, Sanjay!\nWelcome, Li Zhang!\nPlease provide your email.\nWelcome!'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `886a7841-e709-44cf-8230-af92ffc38017` v1
status=in_review difficulty=3 concepts=['dict-mutation-during-iteration'] created_at=2026-07-12T12:22:38.670608+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def update_discounts(invoices):
    for invoice_id, data in list(invoices.items()):
        if data['total'] > 1000:
            invoices[invoice_id]['discount'] = 0.1
        else:
            invoices[invoice_id]['discount'] = 0.05
        if data['customer'] == 'VIP' and invoice_id not in invoices:
            invoices[invoice_id] = {'total': data['total'], 'customer': data['customer'], 'discount': 0.2}

def main():
    invoices = {
        'INV-001': {'total': 1200, 'customer': 'VIP'},
        'INV-002': {'total': 950, 'customer': 'Regular'},
        'INV-003': {'total': 1100, 'customer': 'Regular'}
    }
    update_discounts(invoices)
    for inv_id in sorted(invoices):
        print(f"{inv_id}: {invoices[inv_id]['discount']}")

main()
```
context: A function updates invoice discounts based on total and customer type.

#### Question
What does this code print?
#### Choices
- **a**: INV-001: 0.1
INV-002: 0.05
INV-003: 0.05
- **b**: INV-001: 0.2
INV-002: 0.05
INV-003: 0.1
- **c**: INV-001: 0.1
INV-002: 0.05
INV-003: 0.1 <-- correct
- **d**: INV-001: 0.05
INV-002: 0.05
INV-003: 0.05

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: 'INV-001: 0.1\nINV-002: 0.05\nINV-003: 0.1'

#### Explanation
- summary: The function iterates over a list of the invoice items, so mutating the original dictionary is safe. For each invoice, it assigns a 0.1 discount if total > 1000, otherwise 0.05. The special 'VIP' customer block never runs, because the invoice_id is always present in invoices during the iteration. Thus, only the discounts based on total apply.
- principle: Iterating over a list copy of dict.items() allows safe mutation of the original dictionary during the loop.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output 'INV-001: 0.1\nINV-002: 0.05\nINV-003: 0.1'; the verified output is authoritative regardless)
- why_wrong:
  - **b**: Assumed the 'VIP' customer branch added a new or updated dict entry with 0.2, but the if condition `invoice_id not in invoices` is never true for already-present invoices.
  - **a**: Forgot that total > 1000 gives a 0.1 discount for 'INV-003', even though the customer is 'Regular'.
  - **d**: Ignored the > 1000 condition, applying only the else 0.05 to all invoices.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='INV-001: 0.1\nINV-002: 0.05\nINV-003: 0.1' expected_stdout='INV-001: 0.1\nINV-002: 0.05\nINV-003: 0.1'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `1d1bb4d1-36dc-4062-a9bc-fa9ae2a84dc3` v1
status=in_review difficulty=2 concepts=['float-precision'] created_at=2026-07-12T12:22:56.445862+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def compute_event_rate(count, window_seconds):
    return count / window_seconds

event_counts = [100, 200, 150]
window_lengths = [10, 20, 15]
rates = []
for i in range(len(event_counts)):
    rate = compute_event_rate(event_counts[i], window_lengths[i])
    rates.append(rate)
print(rates)

mean_rate = sum(rates) / len(rates)
print(f"{mean_rate:.2f}")
```
context: This computes per-window event rates and then averages them, typical for analytics.

#### Question
What does this code print?
#### Choices
- **a**: [10, 10, 10]
10
- **b**: [10.0, 10.0, 10.0]
10
- **c**: [10, 10, 10]
10.00
- **d**: [10.0, 10.0, 10.0]
10.00 <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: '[10.0, 10.0, 10.0]\n10.00'

#### Explanation
- summary: The compute_event_rate function divides each count by its window, producing 10.0 three times due to integer division resulting in floats in Python 3. rates contains three 10.0 values. The mean is their average, still 10.0, printed as 10.00 due to f-string formatting.
- principle: In Python 3, dividing two ints with / always yields a float, and f-strings with .2f format float output with two decimal places.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output '[10.0, 10.0, 10.0]\n10.00'; the verified output is authoritative regardless)
- why_wrong:
  - **c**: Assumes Python 3 division of ints gives ints, but it gives floats.
  - **b**: Assumes .2f formatting omits decimals, but it always shows two decimals.
  - **a**: Combines both: expects integer division and no decimals in the mean output.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='[10.0, 10.0, 10.0]\n10.00' expected_stdout='[10.0, 10.0, 10.0]\n10.00'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `f7255949-1cde-4d12-95b6-0629d45fc3a8` v1
status=in_review difficulty=5 concepts=['sorting-stability-assumption'] created_at=2026-07-12T12:23:17.721064+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
from datetime import datetime

events = [
    {"user": "alice", "ts": datetime(2024, 6, 1, 9, 0), "type": "login"},
    {"user": "bob", "ts": datetime(2024, 6, 1, 9, 2), "type": "logout"},
    {"user": "alice", "ts": datetime(2024, 6, 1, 9, 3), "type": "purchase"},
    {"user": "charlie", "ts": datetime(2024, 6, 1, 9, 2), "type": "login"},
    {"user": "bob", "ts": datetime(2024, 6, 1, 9, 4), "type": "login"}
]

# First sort: by event type alphabetically
sorted_events = sorted(events, key=lambda e: e["type"])

# Second sort: by timestamp ascending
sorted_events = sorted(sorted_events, key=lambda e: e["ts"])

for e in sorted_events:
    print(f"{e['user']} {e['type']}")
```
context: Analytics pipeline step: events are sorted for downstream processing.

#### Question
What does this code print?
#### Choices
- **a**: alice login
charlie login
bob logout
alice purchase
bob login <-- correct
- **b**: bob logout
alice login
charlie login
alice purchase
bob login
- **c**: alice login
bob logout
charlie login
alice purchase
bob login
- **d**: alice login
bob logout
bob login
charlie login
alice purchase

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: 'alice login\ncharlie login\nbob logout\nalice purchase\nbob login'

#### Explanation
- summary: First, events are sorted by 'type' field alphabetically, but when the second sort by 'ts' (timestamp) is done, Python's sort is stable: events with equal timestamps retain their 'type' order from the previous sort. This means, for instance, that at timestamp 09:02, if both 'charlie login' and 'bob logout' exist, their relative order from the previous ('type') sort is preserved.
- principle: Python's sorted() is a stable sort: equal-key items retain their previous relative order.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output 'alice login\ncharlie login\nbob logout\nalice purchase\nbob login'; the verified output is authoritative regardless)
- why_wrong:
  - **c**: Assumed all 'login' events group before others, ignoring that second (timestamp) sort determines order except ties; here, 'charlie login' (9:02) and 'bob logout' (9:02) order is stable from the first sort.
  - **b**: Presumed the 'bob logout' would come first because of its 'type', missing that timestamp sort keeps equal times in their type order.
  - **d**: Thought timestamp sort would fully regroup by time, ignoring that only items with equal timestamps retain type-based order (making 'charlie login' precede 'bob logout' at 09:02).

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='alice login\ncharlie login\nbob logout\nalice purchase\nbob login' expected_stdout='alice login\ncharlie login\nbob logout\nalice purchase\nbob login'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `7e371553-e385-4d22-9768-ed8e7de2a4e1` v1
status=in_review difficulty=1 concepts=['float-precision'] created_at=2026-07-12T12:23:46.029219+00:00
quality: solver=pass | solver_confidence=1.0 | clean

#### Code
```python
def reconcile_payments(amounts):
    total = 0.0
    for amt in amounts:
        total += amt
    return total

invoice_amount = 19.50
payments = [10.00, 9.50]
result = reconcile_payments(payments)

if result == invoice_amount:
    print("Payments match invoice")
else:
    print(f"Discrepancy: {invoice_amount - result:.2f}")
```
context: A developer is verifying that the sum of payments matches the invoice amount exactly.

#### Question
What does this code print?
#### Choices
- **a**: Payments match invoice <-- correct
- **b**: Payments match invoice
Discrepancy: 0.00
- **c**: Discrepancy: 0.01
- **d**: Discrepancy: 0.00

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: 'Payments match invoice'

#### Explanation
- summary: The function sums the payment amounts, 10.00 + 9.50, which is exactly 19.50. Python represents these values exactly in binary floating point, so result == invoice_amount is True, and 'Payments match invoice' is printed.
- principle: Some decimal fractions (like 19.50, 10.00, 9.50) are exactly representable as binary floating point, so float equality is reliable in this case.
- mismatch_flagged: False
- why_wrong:
  - **d**: The misconception is that float == always fails, but here the values are exactly equal, so the else branch does not run.
  - **c**: Assumes a visible floating-point error occurs, but with these values the sum is exact.
  - **b**: Believes both print statements could run, which is impossible in an if-else block.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='Payments match invoice' expected_stdout='Payments match invoice'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `75c67371-17ae-4b9c-861e-88d18820a14e` v1
status=in_review difficulty=2 concepts=['global-state-mutation'] created_at=2026-07-12T12:24:01.217912+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
cart_total = 0

def add_to_cart(price):
    global cart_total
    cart_total += price
    print(f"Added: {price}, Total: {cart_total}")

add_to_cart(15)
add_to_cart(10)
print(f"Final total: {cart_total}")
```
context: A minimal checkout service tracks the running total in a global variable.

#### Question
What does this code print?
#### Choices
- **a**: Added: 15, Total: 15
Added: 10, Total: 10
Final total: 25
- **b**: Added: 15, Total: 15
Added: 10, Total: 10
Final total: 10
- **c**: Added: 15, Total: 15
Added: 10, Total: 25
Final total: 10
- **d**: Added: 15, Total: 15
Added: 10, Total: 25
Final total: 25 <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: 'Added: 15, Total: 15\nAdded: 10, Total: 25\nFinal total: 25'

#### Explanation
- summary: cart_total starts at 0. add_to_cart(15) adds 15, prints 'Added: 15, Total: 15'. add_to_cart(10) adds 10 to the global cart_total, making it 25, and prints 'Added: 10, Total: 25'. The final print outputs 'Final total: 25'. The global keyword ensures that the variable is updated across function calls.
- principle: Using 'global' inside a function allows mutation of a module-level variable, persisting state across calls.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output 'Added: 15, Total: 15\nAdded: 10, Total: 25\nFinal total: 25'; the verified output is authoritative regardless)
- why_wrong:
  - **b**: Misses the effect of 'global', as if cart_total were local in the function.
  - **a**: Assumes function doesn't update the global, but the outer variable is updated after both calls.
  - **c**: Assumes the final total only reflects the last added price, not the running sum.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='Added: 15, Total: 15\nAdded: 10, Total: 25\nFinal total: 25' expected_stdout='Added: 15, Total: 15\nAdded: 10, Total: 25\nFinal total: 25'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `a2d3bf03-e388-48b8-be6d-64f4ccf9913c` v1
status=in_review difficulty=5 concepts=['unpacking-order-assumption'] created_at=2026-07-12T12:25:12.906978+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def process_results(results):
    processed = []
    for item in results:
        # Unpack result tuple: status, data, meta
        status, data, meta = item
        if status == 'ok':
            processed.append((data, meta.get('source')))
        else:
            processed.append(('error', meta.get('source')))
    return processed

def get_results():
    # Each tuple is (status, data, meta)
    return [
        ('ok', 42, {'source': 'A'}),
        ('fail', None, {'source': 'B'}),
        ('ok', 13, {'source': 'C', 'extra': 'Z'}),
        ('fail', None, {'source': 'D', 'extra': 'Y'}),
    ]

def summarize(processed):
    ok_count = sum(1 for data, _ in processed if data != 'error')
    sources = [src for _, src in processed]
    print(ok_count)
    print(sources)

if __name__ == '__main__':
    results = get_results()
    # Assume process_results returns list of (data, source) tuples
    processed = process_results(results)
    summarize(processed)
```
context: Processing a list of result tuples from an API call and summarizing.

#### Question
What does this code print?
#### Choices
- **a**: 2
['A', 'C']
- **b**: 2
['A', 'B', 'C', 'D'] <-- correct
- **c**: 2
['A', 'B', 'C', 'D', 'Y', 'Z']
- **d**: 4
['A', 'B', 'C', 'D']

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: "2\n['A', 'B', 'C', 'D']"

#### Explanation
- summary: In process_results, each result tuple is unpacked as (status, data, meta) in the correct order. If status is 'ok', (data, meta['source']) is appended; else ('error', meta['source']) is appended. This results in [('42','A'), ('error','B'), (13,'C'), ('error','D')]. summarize() counts those not equal to 'error' (i.e., 42 and 13) and prints the list of all sources in order. Thus, it prints 2 and ['A','B','C','D'].
- principle: Tuple unpacking uses positional order, not named semantics; incorrect assumptions about order yield misassigned variables.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "2\n['A', 'B', 'C', 'D']"; the verified output is authoritative regardless)
- why_wrong:
  - **c**: This includes meta['extra'] values as sources, misunderstanding tuple unpacking and the processing logic.
  - **d**: Counts all results as ok, ignoring that 'error' replaces data in failed cases.
  - **a**: Filters sources to only those for 'ok' results, but the code appends all sources regardless of status.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="2\n['A', 'B', 'C', 'D']" expected_stdout="2\n['A', 'B', 'C', 'D']"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `f073a006-c7c5-47e6-9f3a-b14b49532d88` v1
status=in_review difficulty=1 concepts=['sorting-stability-assumption'] created_at=2026-07-12T12:25:42.760011+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
features = [
    {'name': 'dark_mode', 'priority': 2},
    {'name': 'beta_search', 'priority': 1},
    {'name': 'ads', 'priority': 2},
]
features.sort(key=lambda f: f['priority'])
for f in features:
    print(f['name'])
```
context: A feature flag service is displaying features by priority.

#### Question
What does this code print?
#### Choices
- **a**: ads
dark_mode
beta_search
- **b**: beta_search
dark_mode
ads <-- correct
- **c**: beta_search
ads
dark_mode
- **d**: dark_mode
beta_search
ads

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: 'beta_search\ndark_mode\nads'

#### Explanation
- summary: The list is sorted by 'priority', so 'beta_search' with priority 1 comes first. The two features with priority 2 ('dark_mode' and 'ads') maintain their original order because Python's sort is stable. The output is the names in the sorted order.
- principle: Python's list.sort() is stable: the relative order of equal keys is preserved.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output 'beta_search\ndark_mode\nads'; the verified output is authoritative regardless)
- why_wrong:
  - **d**: Assumes sorting is not stable and reorders 'dark_mode' and 'ads'.
  - **c**: Assumes sorting is stable but thinks the two priority=2 items reverse order when sorted.
  - **a**: Assumes sorting is in descending order, so highest priority shown first.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='beta_search\ndark_mode\nads' expected_stdout='beta_search\ndark_mode\nads'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `ce8e41c6-19c7-4cca-a59c-aff2c93eca30` v1
status=in_review difficulty=6 concepts=['string-immutability-misuse'] created_at=2026-07-12T12:26:26.948140+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def sanitize_product_names(names):
    sanitized = []
    for i, name in enumerate(names):
        if name.startswith(' '):
            name = name.lstrip()
        if name.endswith(' '):
            name = name.rstrip()
        # Replace dashes with spaces, but only for names with 'SKU' in them
        if 'SKU' in name:
            name = name.replace('-', ' ')
        sanitized.append(name)
    return sanitized

def update_inventory(products):
    # products: list of dict { 'name': str, 'qty': int }
    raw_names = [product['name'] for product in products]
    cleaned_names = sanitize_product_names(raw_names)
    for i, product in enumerate(products):
        # mistakenly tries to update the name directly via the old list
        product['name'] = raw_names[i]
    return products, cleaned_names

products = [
    {'name': '  Widget-SKU-124 ', 'qty': 4},
    {'name': 'Gadget-SKU-233', 'qty': 3},
    {'name': ' SparePart ', 'qty': 10}
]

updated_products, cleaned_names = update_inventory(products)
print([p['name'] for p in updated_products])
print(cleaned_names)
```
context: This code processes and sanitizes product names in an inventory management context.

#### Question
What does this code print?
#### Choices
- **a**: ['  Widget-SKU-124 ', 'Gadget-SKU-233', ' SparePart ']
['Widget SKU 124', 'Gadget SKU 233', 'SparePart'] <-- correct
- **b**: ['Widget SKU 124', 'Gadget SKU 233', 'SparePart']
['Widget SKU 124', 'Gadget SKU 233', 'SparePart']
- **c**: ['Widget-SKU-124', 'Gadget-SKU-233', 'SparePart']
['Widget-SKU-124', 'Gadget-SKU-233', 'SparePart']
- **d**: ['Widget SKU 124 ', 'Gadget SKU 233', 'SparePart']
['Widget SKU 124 ', 'Gadget SKU 233', 'SparePart']

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: "['  Widget-SKU-124 ', 'Gadget-SKU-233', ' SparePart ']\n['Widget SKU 124', 'Gadget SKU 233', 'SparePart']"

#### Explanation
- summary: sanitize_product_names produces a new list of cleaned names, but since strings are immutable, the original product dicts' 'name' fields are not updated; only the cleaned_names list contains the sanitized names. The final print of [p['name'] for p in updated_products] shows the original names, and cleaned_names shows the new, cleaned values.
- principle: Strings in Python are immutable; modifying or stripping returns a new string, and assigning to a list or dict does not retroactively affect previous references.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "['  Widget-SKU-124 ', 'Gadget-SKU-233', ' SparePart ']\n['Widget SKU 124', 'Gadget SKU 233', 'SparePart']"; the verified output is authoritative regardless)
- why_wrong:
  - **b**: Assumes the sanitized strings update the dictionary in-place, but they do not; product['name'] remains unchanged because strings are immutable and updating the list of names does not mutate the dict.
  - **c**: Misses that the replace() is called for SKU-containing names, so the dashes should become spaces.
  - **d**: Mixes up in-place versus non-in-place string operations and fails to remove trailing space from the first item, but rstrip() is indeed called and trailing whitespace is removed for names ending with a space.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="['  Widget-SKU-124 ', 'Gadget-SKU-233', ' SparePart ']\n['Widget SKU 124', 'Gadget SKU 233', 'SparePart']" expected_stdout="['  Widget-SKU-124 ', 'Gadget-SKU-233', ' SparePart ']\n['Widget SKU 124', 'Gadget SKU 233', 'SparePart']"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `e1fbb620-45e0-4b4b-8fb7-358374591171` v1
status=in_review difficulty=2 concepts=['early-return-skipped-path'] created_at=2026-07-12T12:26:42.084434+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def add_points(account, points):
    if points <= 0:
        print('Invalid points')
        return
    account['points'] += points
    print(f"New balance: {account['points']}")

ledger = {'user': 'alice', 'points': 120}
add_points(ledger, 0)
add_points(ledger, 30)
print(f"Final: {ledger['points']}")
```
context: A loyalty program adds points to a user's ledger, but blocks zero or negative deposits.

#### Question
What does this code print?
#### Choices
- **a**: New balance: 120
New balance: 150
Final: 150
- **b**: Invalid points
New balance: 150
Final: 120
- **c**: Invalid points
New balance: 150
Final: 180
- **d**: Invalid points
New balance: 150
Final: 150 <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: 'Invalid points\nNew balance: 150\nFinal: 150'

#### Explanation
- summary: The first add_points call gets 0 points, which triggers the early return after printing 'Invalid points', so no balance is changed. The second adds 30, increasing the balance to 150 and printing 'New balance: 150'. Finally, the balance is printed as 150.
- principle: When a function returns early, any code after 'return' is not executed.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output 'Invalid points\nNew balance: 150\nFinal: 150'; the verified output is authoritative regardless)
- why_wrong:
  - **a**: Assumes no early return, so the balance change also occurs for invalid points.
  - **c**: Thinks the valid add_points call runs twice, likely from ignoring early return or double-adding.
  - **b**: Missed that the account dict is mutated inside the function, so final points are still 120.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='Invalid points\nNew balance: 150\nFinal: 150' expected_stdout='Invalid points\nNew balance: 150\nFinal: 150'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `cd585008-47f9-4c71-baf7-08e5c03ed583` v1
status=in_review difficulty=7 concepts=['shallow-vs-deep-copy'] created_at=2026-07-12T12:27:09.768034+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def pop_cart(cart):
    # Called when a cart is abandoned. Returns order dict for logging, 
    # and removes all items from the cart.
    log = {
        "user": cart["user"],
        "items": cart["items"].copy(),  # Make a shallow copy
        "tags": cart["tags"][:],  # Shallow copy of the tags list
    }
    cart["items"].clear()
    cart["tags"].append("abandoned")
    return log

def worker(snapshots):
    # Snapshots is a list of active carts
    abandoned_orders = []
    for cart in snapshots:
        order = pop_cart(cart)
        abandoned_orders.append(order)
    return abandoned_orders

# Prepare sample carts
cart1 = {
    "user": "alice",
    "items": ["apple", "banana"],
    "tags": ["promo"]
}
cart2 = {
    "user": "bob",
    "items": ["carrot"],
    "tags": ["vip"]
}

snapshot = [cart1.copy(), cart2.copy()]
orders = worker(snapshot)

print(orders[0]["items"])
print(cart1["items"])
print(orders[0]["tags"])
print(cart1["tags"])

```
context: A background worker processes abandoned shopping carts and logs their contents for review.

#### Question
What does this code print?
#### Choices
- **a**: ['apple', 'banana']
['apple', 'banana']
['promo', 'abandoned']
['promo', 'abandoned']
- **b**: ['apple', 'banana']
['apple', 'banana']
['promo']
['promo', 'abandoned']
- **c**: ['apple', 'banana']
[]
['promo']
['promo', 'abandoned'] <-- correct
- **d**: ['apple', 'banana']
[]
['promo', 'abandoned']
['promo', 'abandoned']

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: "['apple', 'banana']\n[]\n['promo']\n['promo', 'abandoned']"

#### Explanation
- summary: The pop_cart function makes a shallow copy of the cart items list (using .copy()), so clearing the original cart's items does not affect the copied list in the log; thus, orders[0]['items'] remains ['apple', 'banana'], while cart1['items'] becomes an empty list. The tags list is sliced to create a new list for the log, so appending to the original cart's tags after that does not affect the log's tags list. cart1['tags'] becomes ['promo', 'abandoned'], but orders[0]['tags'] remains ['promo'].
- principle: A shallow copy of a list (via .copy() or slicing) produces a new list, so further mutations of the original don't affect the copy; but .copy() of a dict is only top-level and does not recursively copy nested structures.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "['apple', 'banana']\n[]\n['promo']\n['promo', 'abandoned']"; the verified output is authoritative regardless)
- why_wrong:
  - **b**: Assumes that clearing cart1['items'] does not affect cart1 because it was copied, but only the log (orders[0]['items']) is a copy; the original list is cleared.
  - **d**: Assumes that log['tags'] is still aliased to cart1['tags'], but slicing creates a new list, so only cart1['tags'] gets 'abandoned' appended.
  - **a**: Assumes both items and tags in both log and cart1 are separated by deep copy, but only shallow copies are made; log['items'] and log['tags'] are new lists, but the original cart's lists are changed by clear and append.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="['apple', 'banana']\n[]\n['promo']\n['promo', 'abandoned']" expected_stdout="['apple', 'banana']\n[]\n['promo']\n['promo', 'abandoned']"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `56d6854c-83e7-49ef-8ede-69c42dfacdae` v1
status=in_review difficulty=8 concepts=['unpacking-order-assumption'] created_at=2026-07-12T12:27:41.679080+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
class AuditLog:
    def __init__(self):
        self.entries = []
    def write(self, *args, actor=None, **kwargs):
        fields = []
        if actor:
            fields.append(f"actor={actor}")
        if args:
            fields.extend(f"arg{i}={v}" for i, v in enumerate(args))
        for k, v in kwargs.items():
            fields.append(f"{k}={v}")
        self.entries.append(", ".join(fields))
    def latest(self):
        return self.entries[-1] if self.entries else None

def process_event(event, log):
    # event: (actor, data_dict) or (data_dict, actor)
    # actor is always str, data_dict always dict
    # But which comes first isn't guaranteed! This function must handle both.
    if isinstance(event[0], str):
        actor, data = event
    else:
        data, actor = event
    log.write(**data, actor=actor)

def main():
    log = AuditLog()
    events = [
        ("alice", {"action": "login", "ip": "10.0.0.1"}),
        ({"action": "delete", "resource": "file.txt"}, "bob"),
        ("carol", {"action": "logout"}),
        ({"action": "update", "resource": "table"}, "dave")
    ]
    for event in events:
        process_event(event, log)
    for entry in log.entries:
        print(entry)

main()
```
context: Audit events arrive in tuples with fields in unpredictable order; code must robustly unpack.

#### Question
What does this code print?
#### Choices
- **a**: actor=alice, action=login, ip=10.0.0.1
actor=bob, action=delete, resource=file.txt
actor=carol, action=logout
actor=dave, action=update, resource=table <-- correct
- **b**: actor=alice, action=login, ip=10.0.0.1
action=delete, resource=file.txt, actor=bob
actor=carol, action=logout
resource=table, action=update, actor=dave
- **c**: actor=alice, action=login, ip=10.0.0.1
actor=bob, resource=file.txt, action=delete
actor=carol, action=logout
actor=dave, resource=table, action=update
- **d**: actor=alice, action=login, ip=10.0.0.1
actor=delete, action=bob, resource=file.txt
actor=carol, action=logout
actor=update, action=dave, resource=table

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: 'actor=alice, action=login, ip=10.0.0.1\nactor=bob, action=delete, resource=file.txt\nactor=carol, action=logout\nactor=dave, action=update, resource=table'

#### Explanation
- summary: The code robustly checks the type of the first tuple element to decide which is actor and which is data, ensuring correct unpacking regardless of tuple order. The write method then builds the audit log entry with actor first (if present), then in the order that **data dict provides its keys (insertion order, per Python 3.7+). Thus, each entry is actor=X, action=Y, ... in the correct order.
- principle: Unpacking with isinstance checks allows safe disambiguation of tuple element roles, and **kwargs preserves insertion order when iterating over dicts in Python 3.7+.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output 'actor=alice, action=login, ip=10.0.0.1\nactor=bob, action=delete, resource=file.txt\nactor=carol, action=logout\nactor=dave, action=update, resource=table'; the verified output is authoritative regardless)
- why_wrong:
  - **d**: Assumes positional unpacking always puts the first tuple item into actor, leading to dicts as actor and strings as data in those cases, so field labels are mismatched.
  - **b**: Incorrectly assumes dict unpacking with **kwargs does not preserve insertion order, so field order is jumbled.
  - **c**: Assumes **kwargs keys are always sorted alphabetically, so output field order is actor, resource, action.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured='actor=alice, action=login, ip=10.0.0.1\nactor=bob, action=delete, resource=file.txt\nactor=carol, action=logout\nactor=dave, action=update, resource=table' expected_stdout='actor=alice, action=login, ip=10.0.0.1\nactor=bob, action=delete, resource=file.txt\nactor=carol, action=logout\nactor=dave, action=update, resource=table'
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `6ecc1d0e-c944-43d9-9748-fd5ad5403ecf` v1
status=in_review difficulty=10 concepts=['shallow-vs-deep-copy'] created_at=2026-07-12T12:28:37.821031+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
class Cart:
    def __init__(self, items=None, discounts=None):
        self.items = items if items else []
        self.discounts = discounts if discounts else {}

    def add_item(self, product, quantity):
        self.items.append({'product': product, 'quantity': quantity})

    def apply_discount(self, code, percent):
        self.discounts[code] = percent

    def copy(self):
        import copy
        return Cart(copy.deepcopy(self.items), self.discounts.copy())

    def __str__(self):
        return f"items={self.items}, discounts={self.discounts}"

def checkout_session(original_cart):
    session_cart = original_cart.copy()
    session_cart.add_item('USB Cable', 2)
    session_cart.apply_discount('SPRINGSALE', 10)
    return session_cart

# Initial cart setup
cart = Cart()
cart.add_item('Laptop', 1)
cart.apply_discount('WELCOME', 5)

# Simulate a checkout session
final_cart = checkout_session(cart)

# Mutate the original cart after the session
cart.add_item('Mouse', 1)
cart.apply_discount('BONUS', 15)

print(str(cart))
print(str(final_cart))
```
context: In a checkout service, a user's cart and discounts may be copied for a session.

#### Question
What does this code print?
#### Choices
- **a**: items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'Mouse', 'quantity': 1}], discounts={'WELCOME': 5, 'BONUS': 15}
items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'USB Cable', 'quantity': 2}], discounts={'WELCOME': 5, 'SPRINGSALE': 10} <-- correct
- **b**: items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'Mouse', 'quantity': 1}], discounts={'WELCOME': 5, 'BONUS': 15}
items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'USB Cable', 'quantity': 2}], discounts={'WELCOME': 5, 'BONUS': 15, 'SPRINGSALE': 10}
- **c**: items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'Mouse', 'quantity': 1}], discounts={'WELCOME': 5, 'BONUS': 15}
items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'USB Cable', 'quantity': 2}], discounts={'WELCOME': 5, 'BONUS': 15}
- **d**: items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'Mouse', 'quantity': 1}], discounts={'WELCOME': 5, 'BONUS': 15}
items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'USB Cable', 'quantity': 2}, {'product': 'Mouse', 'quantity': 1}], discounts={'WELCOME': 5, 'SPRINGSALE': 10, 'BONUS': 15}

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: "items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'Mouse', 'quantity': 1}], discounts={'WELCOME': 5, 'BONUS': 15}\nitems=[{'product': 'Laptop', 'quantity': 1}, {'product': 'USB Cable', 'quantity': 2}], discounts={'WELCOME': 5, 'SPRINGSALE': 10}"

#### Explanation
- summary: The Cart.copy() method performs a deep copy of items but only a shallow ('.copy()') copy of discounts, so subsequent mutations of cart.items do not affect final_cart.items, but changes to cart.discounts after the copy do not affect final_cart.discounts either because dict.copy() produces a new dict. When each print runs, cart has both 'Mouse' and 'BONUS', while final_cart has the session's 'USB Cable' and 'SPRINGSALE', with no cross-contamination.
- principle: deepcopy makes items independent between the original and copied cart, while dict.copy() makes discounts independent at the first level.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'Mouse', 'quantity': 1}], discounts={'WELCOME': 5, 'BONUS': 15}\nitems=[{'product': 'Laptop', 'quantity': 1}, {'product': 'USB Cable', 'quantity': 2}], discounts={'WELCOME': 5, 'SPRINGSALE': 10}"; the verified output is authoritative regardless)
- why_wrong:
  - **d**: Assumes items were shallow-copied, so 'Mouse' is added to both carts and discounts are merged, but items is a deep copy so only cart gets 'Mouse'.
  - **b**: Assumes discount dicts are not independent at all, so all keys appear in both; actually dict.copy() makes separate dicts for future mutations.
  - **c**: Assumes discounts are only updated on cart, not the session, so session_cart misses 'SPRINGSALE'; but session_cart gets its own discounts copy and is updated inside the session.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'Mouse', 'quantity': 1}], discounts={'WELCOME': 5, 'BONUS': 15}\nitems=[{'product': 'Laptop', 'quantity': 1}, {'product': 'USB Cable', 'quantity': 2}], discounts={'WELCOME': 5, 'SPRINGSALE': 10}" expected_stdout="items=[{'product': 'Laptop', 'quantity': 1}, {'product': 'Mouse', 'quantity': 1}], discounts={'WELCOME': 5, 'BONUS': 15}\nitems=[{'product': 'Laptop', 'quantity': 1}, {'product': 'USB Cable', 'quantity': 2}], discounts={'WELCOME': 5, 'SPRINGSALE': 10}"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### trace -- `b6626824-8b0b-4287-9d4b-19a7c4b8da36` v1
status=in_review difficulty=6 concepts=['list-mutation-during-iteration'] created_at=2026-07-12T12:29:18.667369+00:00
quality: solver=pass | solver_confidence=1.0 | FLAGS: explanation_mismatch

#### Code
```python
def onboard_users(users):
    unverified = []
    onboarded = []
    for user in users:
        if not user['email_verified']:
            unverified.append(user)
            continue
        onboarded.append(user)

    for user in unverified:
        # Simulate verification step
        if user['email'].endswith('@example.com'):
            user['email_verified'] = True
            onboarded.append(user)

    print([u['email'] for u in onboarded])

users = [
    {'email': 'alice@example.com', 'email_verified': False},
    {'email': 'bob@example.org', 'email_verified': True},
    {'email': 'carol@example.com', 'email_verified': False},
    {'email': 'dan@example.com', 'email_verified': True}
]

onboard_users(users)
```
context: This checks which users are considered onboarded after simulating email verification.

#### Question
What does this code print?
#### Choices
- **a**: ['bob@example.org', 'dan@example.com']
- **b**: ['bob@example.org', 'dan@example.com', 'alice@example.com', 'carol@example.com'] <-- correct
- **c**: ['bob@example.org', 'dan@example.com', 'carol@example.com']
- **d**: ['bob@example.org', 'dan@example.com', 'alice@example.com']

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: "['bob@example.org', 'dan@example.com', 'alice@example.com', 'carol@example.com']"

#### Explanation
- summary: The code processes users in two passes: first, it appends pre-verified users to onboarded and collects unverified users. Then, it simulates email verification for those unverified users whose email ends with @example.com and appends them to onboarded. Both alice@example.com and carol@example.com qualify in this step, so the final onboarded list contains four emails.
- principle: Mutating objects in a list while iterating over a copy or different list (not the one being iterated) is safe and all intended objects are processed.
- mismatch_flagged: True (draft_explanation.summary does not literally reference the sandbox-captured output "['bob@example.org', 'dan@example.com', 'alice@example.com', 'carol@example.com']"; the verified output is authoritative regardless)
- why_wrong:
  - **a**: Misses that the second loop can successfully verify and append both alice@example.com and carol@example.com.
  - **c**: Overlooks that both alice and carol are unverified and match the domain, not just carol.
  - **d**: Assumes only alice@example.com passes second-loop verification, ignoring carol@example.com.

#### Sandbox checks
- [x] code_runs_clean
- [x] deterministic_double_run
- [x] captured_output_matches_claim -- captured="['bob@example.org', 'dan@example.com', 'alice@example.com', 'carol@example.com']" expected_stdout="['bob@example.org', 'dan@example.com', 'alice@example.com', 'carol@example.com']"
- [x] captured_output_distinct_from_distractors

#### Semantic gate verdicts
- **solver**: pass -- solver matched the answer key

---

### predict_the_fix -- `e28cc1a5-bb8a-46cc-9960-312e21c765f8` v1
status=in_review difficulty=3 concepts=['mutable-default-arg'] created_at=2026-07-12T14:20:28.610443+00:00
quality: clean

#### Code
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
context: Records events for an audit trail. Called once per request.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def record_event(name, payload, history=[]):
    if history is None:
        history = []
    entry = {"name": name, "payload": payload}
    history.append(entry)
    if len(history) > 100:
        history.pop(0)
    return history


def summarize(history):
    return [item["name"] for item in history]

- **b**: def record_event(name, payload, history=[]):
    entry = {"name": name, "payload": payload}
    history.append(entry)
    if len(history) > 100:
        history.pop(0)
    return list(history)


def summarize(history):
    return [item["name"] for item in history]

- **c**: def record_event(name, payload, history=None):
    if history is None:
        history = []
    entry = {"name": name, "payload": payload}
    history.append(entry)
    if len(history) > 100:
        history.pop(0)
    return history


def summarize(history):
    return [item["name"] for item in history]
 <-- correct
- **d**: def record_event(name, payload, history=[]):
    entry = {"name": name, "payload": payload}
    history.append(entry)
    if len(history) >= 100:
        history.pop(0)
    return history


def summarize(history):
    return [item["name"] for item in history]


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: None

#### Explanation
- summary: Default argument values are evaluated once, when the function object is created. The empty list therefore belongs to the function, not to the call, so every call that omits the argument appends to the same list.
- principle: Default arguments are evaluated at definition time. Never default to a mutable object.
- mismatch_flagged: False
- why_wrong:
  - **a**: Adds the None guard from the usual remedy but leaves the default as a literal list, so the guard never fires.
  - **b**: Hands back a copy, but the shared default is still the object being appended to on every call.
  - **d**: Tightens the trim boundary, which has nothing to do with the history surviving between calls.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 14, in <module>
AssertionError: a call without a history should start empty

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 16, in <module>
AssertionError: a call without a history should start empty

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 14, in <module>
AssertionError: a call without a history should start empty

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 14, in <module>
AssertionError: a call without a history should start empty

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `df68ea78-f178-4a0c-941d-e5fcbca10b77` v1
status=in_review difficulty=6 concepts=['shallow-vs-deep-copy'] created_at=2026-07-12T14:20:35.352059+00:00
quality: clean

#### Code
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
context: Builds a per-tenant report template from a shared set of defaults.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: class TemplateStore:
    def __init__(self, defaults):
        self.defaults = defaults

    def clone(self):
        return {**self.defaults}

    def customize(self, overrides):
        draft = self.clone()
        for key, value in overrides.items():
            if isinstance(value, dict):
                draft[key].update(value)
            else:
                draft[key] = value
        return draft

- **b**: class TemplateStore:
    def __init__(self, defaults):
        self.defaults = defaults

    def clone(self):
        return self.defaults.copy()

    def customize(self, overrides):
        draft = self.clone()
        for key, value in overrides.items():
            if isinstance(value, dict):
                draft[key].update(value)
            else:
                draft[key] = value
        return draft

- **c**: class TemplateStore:
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
 <-- correct
- **d**: class TemplateStore:
    def __init__(self, defaults):
        self.defaults = defaults

    def clone(self):
        return dict(self.defaults)

    def customize(self, overrides):
        draft = self.clone()
        for key, value in overrides.items():
            if isinstance(value, dict):
                draft[key].update(dict(value))
            else:
                draft[key] = value
        return draft


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: None

#### Explanation
- summary: dict(self.defaults) copies the outer mapping but not the values inside it, so the nested header dict is the very same object held by the defaults. Updating it in place mutates the defaults, and every later call inherits that change.
- principle: A shallow copy duplicates the container, not the objects inside it. Rebuild nested values before mutating them.
- mismatch_flagged: False
- why_wrong:
  - **a**: Copies the outer dict a second time; the nested value inside it is still shared with the defaults.
  - **b**: Swaps in the copy() method, which is still a one-level copy: the nested dict is the same object.
  - **d**: Copies the incoming override rather than the nested default it is about to write into.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: defaults survive an earlier customization

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: defaults survive an earlier customization

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: defaults survive an earlier customization

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: defaults survive an earlier customization

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `9537ac46-2432-4894-a688-37727fc08442` v1
status=in_review difficulty=5 concepts=['truthy-falsy-empty-check'] created_at=2026-07-12T14:20:41.358581+00:00
quality: clean

#### Code
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
context: Resolves the retry limit for a route. Zero means the route is never retried.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: class RetryPolicy:
    def __init__(self, defaults):
        self.defaults = defaults

    def limit_for(self, route, overrides):
        configured = overrides.get(route)
        if route not in overrides or not configured:
            return self.defaults["limit"]
        return configured

    def describe(self, route, overrides):
        return "{}:{}".format(route, self.limit_for(route, overrides))

- **b**: class RetryPolicy:
    def __init__(self, defaults):
        self.defaults = defaults

    def limit_for(self, route, overrides):
        configured = overrides.get(route, self.defaults["limit"])
        if not configured:
            return self.defaults["limit"]
        return configured

    def describe(self, route, overrides):
        return "{}:{}".format(route, self.limit_for(route, overrides))

- **c**: class RetryPolicy:
    def __init__(self, defaults):
        self.defaults = defaults

    def limit_for(self, route, overrides):
        configured = overrides.get(route)
        if configured is None:
            return self.defaults["limit"]
        return configured

    def describe(self, route, overrides):
        return "{}:{}".format(route, self.limit_for(route, overrides))
 <-- correct
- **d**: class RetryPolicy:
    def __init__(self, defaults):
        self.defaults = defaults

    def limit_for(self, route, overrides):
        configured = overrides.get(route) or self.defaults["limit"]
        if not configured:
            return self.defaults["limit"]
        return configured

    def describe(self, route, overrides):
        return "{}:{}".format(route, self.limit_for(route, overrides))


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: None

#### Explanation
- summary: A truthiness test cannot distinguish a configured 0 from a missing key, because both are falsy. A route explicitly set to zero retries therefore silently receives the default of three.
- principle: Test for absence with `is None`, not with truthiness, whenever 0, empty string, or empty collection is a legitimate value.
- mismatch_flagged: False
- why_wrong:
  - **a**: Adds a membership check, which is true here; the falsy test that actually discards the zero is untouched.
  - **b**: Moves the default into get(), but the truthiness test below still discards an explicit zero.
  - **d**: Uses or to supply the default, which is the same falsy test written a different way.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 16, in <module>
AssertionError: an explicit zero is honoured

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 16, in <module>
AssertionError: an explicit zero is honoured

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 16, in <module>
AssertionError: an explicit zero is honoured

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 16, in <module>
AssertionError: an explicit zero is honoured

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `13c269b8-a496-4a1f-8ddf-3d1d5689f3d6` v1
status=in_review difficulty=4 concepts=['key-function-misuse'] created_at=2026-07-12T14:20:53.378868+00:00
quality: clean

#### Code
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
context: Picks the hottest endpoint from a window of access-log entries.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def tally(events):
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
    return ranked[0][1]


def summary(events):
    return {
        "counts": tally(events),
        "busiest": busiest_endpoint(events),
    }

- **b**: def tally(events):
    counts = {}
    for event in events:
        name = event["endpoint"]
        counts[name] = counts.get(name, 0) + 1
    return counts


def busiest_endpoint(events):
    counts = tally(events)
    if not counts:
        return None
    return max(counts, key=lambda name: name)


def summary(events):
    return {
        "counts": tally(events),
        "busiest": busiest_endpoint(events),
    }

- **c**: def tally(events):
    counts = {}
    for event in events:
        name = event["endpoint"]
        counts[name] = counts.get(name, 0) + 1
    return counts


def busiest_endpoint(events):
    counts = tally(events)
    if not counts:
        return None
    ranked = sorted(counts, reverse=True)
    return ranked[0]


def summary(events):
    return {
        "counts": tally(events),
        "busiest": busiest_endpoint(events),
    }

- **d**: def tally(events):
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
 <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: None

#### Explanation
- summary: items() yields (endpoint, count) pairs. Indexing the pair at 0 selects the endpoint, so the descending sort ranks the endpoints alphabetically and the winner is whichever name sorts last, not whichever endpoint was hit most.
- principle: A sort key must return the quantity you are ranking by, not merely something derived from the same record.
- mismatch_flagged: False
- why_wrong:
  - **a**: Reads the other half of the pair off the winner, but the winner was still chosen alphabetically.
  - **b**: Swaps sorted() for max() but keeps ranking by the endpoint name rather than the hit count.
  - **c**: Sorts the keys directly, which is the same alphabetical ordering with the counts thrown away.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 30, in <module>
AssertionError: the endpoint with the most hits should win

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 30, in <module>
AssertionError: the endpoint with the most hits should win

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 30, in <module>
AssertionError: the endpoint with the most hits should win

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 29, in <module>
AssertionError: the endpoint with the most hits should win

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `7307f9c7-a83a-45af-943c-819107bdd1d0` v1
status=in_review difficulty=4 concepts=['is-vs-equality'] created_at=2026-07-12T14:21:05.473571+00:00
quality: clean

#### Code
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
context: Finds where a given row sits inside a freshly parsed table.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def find_row(rows, target):
    for position, row in enumerate(rows):
        if row is not None and row is target:
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

- **b**: def find_row(rows, target):
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
 <-- correct
- **c**: def find_row(rows, target):
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
        "position": find_row(rows, list(target)),
    }

- **d**: def find_row(rows, target):
    for position, row in enumerate(rows):
        if tuple(row) is tuple(target):
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


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: None

#### Explanation
- summary: parse_rows() builds brand-new list objects. The caller's target is a separate object that merely holds the same numbers, so an identity test is False for every row and the search reports failure.
- principle: Identity asks 'the same object?'. Equality asks 'the same value?'. Data comparison almost always wants the second.
- mismatch_flagged: False
- why_wrong:
  - **a**: Adds a None guard in front of an identity test that was never going to succeed.
  - **c**: Normalises the target into a list, producing yet another distinct object for the identity test to miss.
  - **d**: Converts both sides to tuples, which builds two new objects that are still not the same object.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 23, in <module>
AssertionError: the matching row should be found by value

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 23, in <module>
AssertionError: the matching row should be found by value

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 23, in <module>
AssertionError: the matching row should be found by value

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 23, in <module>
AssertionError: the matching row should be found by value

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `138177ad-9d73-4c35-8734-b34b719c4762` v1
status=in_review difficulty=4 concepts=['global-state-mutation'] created_at=2026-07-12T14:21:11.424722+00:00
quality: clean

#### Code
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
context: Layers a caller's settings on top of the service defaults before a run.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: BASE_CONFIG = {
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
 <-- correct
- **b**: BASE_CONFIG = {
    "retries": 3,
    "timeout": 30,
}


def with_overrides(overrides):
    config = BASE_CONFIG
    config.update(dict(overrides))
    return config


def describe(config):
    parts = []
    for key in sorted(config):
        parts.append(key + "=" + str(config[key]))
    return " ".join(parts)


def run_twice(first, second):
    with_overrides(first)
    return describe(with_overrides(second))

- **c**: BASE_CONFIG = {
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
    with_overrides(dict(first))
    return describe(with_overrides(second))

- **d**: BASE_CONFIG = {
    "retries": 3,
    "timeout": 30,
}


def with_overrides(overrides):
    config = BASE_CONFIG
    config.update(overrides)
    return dict(config)


def describe(config):
    parts = []
    for key in sorted(config):
        parts.append(key + "=" + str(config[key]))
    return " ".join(parts)


def run_twice(first, second):
    with_overrides(first)
    return describe(with_overrides(second))


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: None

#### Explanation
- summary: Assignment in Python binds a name; it does not copy. config and BASE_CONFIG therefore refer to one dictionary, and update() rewrites it in place. The first caller's override becomes the new default for everyone who follows.
- principle: Assignment binds, it does not copy. To leave a shared structure intact, copy it before mutating.
- mismatch_flagged: False
- why_wrong:
  - **b**: Copies the overrides, which were never the shared object; the defaults are still updated in place.
  - **c**: Copies the caller's first payload, which does not stop the defaults being rewritten by the update.
  - **d**: Copies on the way out, long after the module-level dictionary has already been overwritten in place.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: a later call should not inherit an earlier override

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: a later call should not inherit an earlier override

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: a later call should not inherit an earlier override

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: a later call should not inherit an earlier override

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `8692c4aa-9239-44d1-919d-3754d7d20486` v1
status=in_review difficulty=4 concepts=['list-mutation-during-iteration'] created_at=2026-07-12T14:21:26.354963+00:00
quality: clean

#### Code
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
context: Cleans a batch of parsed spreadsheet rows before they are rendered.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def drop_blank_rows(rows):
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
 <-- correct
- **b**: def drop_blank_rows(rows):
    kept = []
    for row in reversed(rows):
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

- **c**: def drop_blank_rows(rows):
    kept = []
    for row in rows:
        if not row:
            rows.pop(rows.index(row))
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

- **d**: def drop_blank_rows(rows):
    kept = []
    for row in rows:
        if not row:
            rows.remove(row)
            continue
        kept.append(list(row))
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


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: a
- captured_stdout: None

#### Explanation
- summary: The blank rows are already excluded by the continue, so nothing needs deleting. The deletion is pure damage: it shortens the list the for-loop is walking, every later element slides down one index, and the loop's counter marches straight past whatever landed in the gap.
- principle: Never delete from a sequence you are iterating. If you are building a new list anyway, you do not need to.
- mismatch_flagged: False
- why_wrong:
  - **b**: Walks the list backwards, which survives the deletion but hands the rows back in the reverse order.
  - **c**: Swaps remove() for pop() with an explicit index, which shortens the list being walked in exactly the same way.
  - **d**: Copies each row on the way into the result, which does nothing about the list being shortened underneath the walk.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 27, in <module>
AssertionError: no populated row should be lost

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 27, in <module>
AssertionError: no populated row should be lost

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 27, in <module>
AssertionError: no populated row should be lost

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 27, in <module>
AssertionError: no populated row should be lost

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `c78d7841-f812-4c18-95b7-87321c7fa3ab` v1
status=in_review difficulty=4 concepts=['dict-mutation-during-iteration'] created_at=2026-07-12T14:21:32.717224+00:00
quality: clean

#### Code
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
context: Keeps only the words that appear often enough to be worth reporting.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def tally(words):
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return counts


def prune(counts, floor):
    kept = {}
    for key in counts:
        if counts[key] < floor:
            counts.pop(key)
            continue
        kept[key] = counts[key]
    return kept


def frequent(words, floor):
    return prune(tally(words), floor)

- **b**: def tally(words):
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return counts


def prune(counts, floor):
    kept = {}
    for key in counts:
        if counts[key] <= floor:
            del counts[key]
            continue
        kept[key] = counts[key]
    return kept


def frequent(words, floor):
    return prune(tally(words), floor)

- **c**: def tally(words):
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return counts


def prune(counts, floor):
    kept = {}
    for key in counts.keys():
        if counts[key] < floor:
            del counts[key]
            continue
        kept[key] = counts[key]
    return kept


def frequent(words, floor):
    return prune(tally(words), floor)

- **d**: def tally(words):
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
 <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: None

#### Explanation
- summary: The rare entries are already excluded by the continue, so the deletion achieves nothing except to change the size of the dictionary mid-walk. CPython detects that and raises RuntimeError on the next step, so the whole call dies rather than returning a slightly wrong answer.
- principle: Never add to or delete from a dictionary you are iterating. Walk a snapshot of the keys, or build a new dictionary.
- mismatch_flagged: False
- why_wrong:
  - **a**: Swaps del for pop(), which removes the entry and changes the size just the same.
  - **b**: Loosens the floor comparison, which changes which entries are dropped but not that dropping them breaks the walk.
  - **c**: Iterates keys() explicitly, which is the same live view over the dictionary being resized.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: rare words should be pruned without disturbing the walk

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: rare words should be pruned without disturbing the walk

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: rare words should be pruned without disturbing the walk

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
AssertionError: rare words should be pruned without disturbing the walk

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `f52e284c-d5aa-4229-8f33-c29dca9946e5` v1
status=in_review difficulty=3 concepts=['string-formatting-mismatch'] created_at=2026-07-12T14:21:39.921648+00:00
quality: clean

#### Code
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
context: Renders a leaderboard line for each competitor. Scores carry one decimal place.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def render(row):
    return "%s scored %d" % (row["name"], round(row["score"]))


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

- **b**: def render(row):
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
 <-- correct
- **c**: def render(row):
    return "%s scored %.0f" % (row["name"], row["score"])


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

- **d**: def render(row):
    return "%s scored %i" % (row["name"], row["score"])


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


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: None

#### Explanation
- summary: The %d conversion asks for an integer. Handed a float it does not complain; it quietly truncates towards zero. Every half point in the competition disappears from the board and nothing anywhere reports an error.
- principle: A conversion specifier is a coercion, not an assertion. Match it to the type you actually hold.
- mismatch_flagged: False
- why_wrong:
  - **a**: Rounds the score before handing it over, which still delivers a whole number to a whole-number conversion.
  - **c**: Switches to a float conversion but asks for no decimal places, so the half point is rounded away instead of truncated.
  - **d**: Uses the other integer conversion, which truncates the score in precisely the same way.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: a half point should survive rendering

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: a half point should survive rendering

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: a half point should survive rendering

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: a half point should survive rendering

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `241f86cd-c6e5-45f0-a5dd-bc92a4f52f63` v1
status=in_review difficulty=4 concepts=['memoization-cache-staleness'] created_at=2026-07-12T14:21:46.196016+00:00
quality: clean

#### Code
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
context: Prices an item at several customer tiers. The cache exists because base lookups are expensive.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: _CACHE = {}


def cache_key(item, multiplier):
    return item["sku"] + ":" + str(item["base"])


def price(item, multiplier):
    key = cache_key(item, multiplier)
    if key in _CACHE:
        return _CACHE[key]
    value = item["base"] * multiplier
    _CACHE[key] = value
    return value


def quote(item, multipliers):
    return [price(item, multiplier) for multiplier in multipliers]

- **b**: _CACHE = {}


def cache_key(item, multiplier):
    return item["sku"]


def price(item, multiplier):
    key = cache_key(item, multiplier)
    if key in _CACHE:
        return _CACHE[key]
    value = item["base"] * multiplier
    _CACHE.setdefault(key, value)
    return value


def quote(item, multipliers):
    return [price(item, multiplier) for multiplier in multipliers]

- **c**: _CACHE = {}


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
 <-- correct
- **d**: _CACHE = {}


def cache_key(item, multiplier):
    return str(item)


def price(item, multiplier):
    key = cache_key(item, multiplier)
    if key in _CACHE:
        return _CACHE[key]
    value = item["base"] * multiplier
    _CACHE[key] = value
    return value


def quote(item, multipliers):
    return [price(item, multiplier) for multiplier in multipliers]


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: None

#### Explanation
- summary: A memo key must capture every input the result depends on. This one captures the item and forgets the multiplier, so the first tier priced wins forever and every subsequent tier is answered with a value computed for someone else.
- principle: The cache key must include every argument the cached value depends on. If it does not, the cache is a source of wrong answers.
- mismatch_flagged: False
- why_wrong:
  - **a**: Adds the base price to the key, which is the same for both tiers; the multiplier is still missing.
  - **b**: Writes with setdefault so an existing entry is never overwritten, which is what was already happening.
  - **d**: Keys on the whole item, which is also identical across the two tiers being priced.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 21, in <module>
AssertionError: a different multiplier should be priced, not served from cache

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 21, in <module>
AssertionError: a different multiplier should be priced, not served from cache

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 21, in <module>
AssertionError: a different multiplier should be priced, not served from cache

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 21, in <module>
AssertionError: a different multiplier should be priced, not served from cache

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `10900108-ac59-4861-83d2-372920a5c88e` v1
status=in_review difficulty=4 concepts=['encoding-decoding-mismatch'] created_at=2026-07-12T14:21:52.473284+00:00
quality: clean

#### Code
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
context: Carries text over a byte channel and reads it back on the far side.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def to_bytes(text):
    return text.encode("utf-8")


def to_text(data):
    return data.decode("ascii", errors="replace")


def roundtrip(text):
    return to_text(to_bytes(text))


def audit(messages):
    lengths = []
    for message in messages:
        lengths.append(len(roundtrip(message)))
    return lengths

- **b**: def to_bytes(text):
    return text.encode("utf-8")


def to_text(data):
    return data.decode("latin-1", errors="ignore")


def roundtrip(text):
    return to_text(to_bytes(text))


def audit(messages):
    lengths = []
    for message in messages:
        lengths.append(len(roundtrip(message)))
    return lengths

- **c**: def to_bytes(text):
    return text.encode("utf-8", errors="replace")


def to_text(data):
    return data.decode("latin-1")


def roundtrip(text):
    return to_text(to_bytes(text))


def audit(messages):
    lengths = []
    for message in messages:
        lengths.append(len(roundtrip(message)))
    return lengths

- **d**: def to_bytes(text):
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
 <-- correct

#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: d
- captured_stdout: None

#### Explanation
- summary: The writer spends two bytes on the accented character; the reader is told each byte is a whole character in a single-byte codec. Nothing raises. The text simply comes back one character longer than it went in, and the corruption travels quietly downstream.
- principle: The codec that reads must be the codec that wrote. A mismatch is silent, not fatal.
- mismatch_flagged: False
- why_wrong:
  - **a**: Reads back as ASCII with replacement, which is a third codec rather than the one that wrote the bytes.
  - **b**: Suppresses decoding errors, but the mismatched codec never raised one: it silently produced the wrong text.
  - **c**: Adds a replacement policy on the writing side; the reader is still using a different codec.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: a round trip should hand back what it was given

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: a round trip should hand back what it was given

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: a round trip should hand back what it was given

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 20, in <module>
AssertionError: a round trip should hand back what it was given

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `53c81087-ebe8-4712-bfda-488fac2e79f8` v1
status=in_review difficulty=4 concepts=['mutable-default-arg'] created_at=2026-07-12T14:22:06.286260+00:00
quality: clean

#### Code
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
context: Collects the timing of each step of a request, so the slowest can be reported.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: def trace(name, duration, spans={}):
    spans[name] = duration
    return dict(spans)


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

- **b**: def trace(name, duration, spans=None):
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
 <-- correct
- **c**: def trace(name, duration, spans={}):
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

- **d**: def trace(name, duration, spans={}):
    spans.setdefault(name, duration)
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


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: b
- captured_stdout: None

#### Explanation
- summary: A default argument is evaluated once, when the def statement runs. The dictionary therefore belongs to the function, not to the call, and every request that omits it writes into the same object. Yesterday's spans turn up in today's trace.
- principle: Default arguments are evaluated at definition time. Never default to a mutable object.
- mismatch_flagged: False
- why_wrong:
  - **a**: Returns a copy, which leaves the caller with fresh data but keeps writing into the one shared default.
  - **c**: Adds the None guard from the usual remedy while leaving the default as a literal dict, so the guard is dead code.
  - **d**: Uses setdefault so an existing span is never overwritten, which was never how the earlier request's span got in.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: a new request should start with no spans

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 24, in <module>
AssertionError: a new request should start with no spans

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: a new request should start with no spans

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
AssertionError: a new request should start with no spans

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)

---

### predict_the_fix -- `23b69b00-043c-4a8a-a9af-786803b84ead` v1
status=in_review difficulty=4 concepts=['string-vs-bytes-confusion'] created_at=2026-07-12T14:22:11.863774+00:00
quality: clean

#### Code
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
context: Prepares labels for a binary record format that budgets ten bytes per field.

#### Question
The test below fails on this code. Which change makes the test pass?
#### Choices
- **a**: FIELD_BYTES = 10


def pack_field(text, limit):
    encoded = text.encode("ascii", errors="ignore")
    if len(text) > limit:
        return None
    return encoded


def pack(records):
    packed = []
    for record in records:
        label = record["label"]
        packed.append(pack_field(label, FIELD_BYTES))
    return packed

- **b**: FIELD_BYTES = 10


def pack_field(text, limit):
    encoded = text.encode("utf-8")
    if len(text) > limit:
        return None
    return encoded


def pack(records):
    packed = []
    for record in records:
        label = record["label"]
        packed.append(pack_field(label.strip(), FIELD_BYTES))
    return packed

- **c**: FIELD_BYTES = 10


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
 <-- correct
- **d**: FIELD_BYTES = 10


def pack_field(text, limit):
    encoded = text.encode("utf-8")
    if len(text.encode("ascii", errors="ignore")) > limit:
        return None
    return encoded


def pack(records):
    packed = []
    for record in records:
        label = record["label"]
        packed.append(pack_field(label, FIELD_BYTES))
    return packed


#### Verified answer key (sandbox-captured stdout)
- correct_choice_id: c
- captured_stdout: None

#### Explanation
- summary: The line above produces the bytes that will actually be written, but the guard measures the string those bytes came from. A str counts characters; the field counts bytes. UTF-8 spends one byte on ASCII and two or more on anything else, so an over-long label sails through the check and is silently written past the end of its field.
- principle: Measure the thing you are about to store, in the unit the destination counts.
- mismatch_flagged: False
- why_wrong:
  - **a**: Writes ASCII bytes instead, which shortens the payload but still measures the unencoded string.
  - **b**: Trims the label before packing it, which changes nothing for a label that has no surrounding whitespace.
  - **d**: Measures the ASCII-only encoding, which drops the very character that made the label overrun.

#### Sandbox checks
- [x] correct_fix_passes_test
- [x] buggy_fails_test -- Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the label overruns a ten-byte field

- [x] distractor_0_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the label overruns a ten-byte field

- [x] distractor_1_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the label overruns a ten-byte field

- [x] distractor_2_still_fails_test -- exit=1 Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
AssertionError: the label overruns a ten-byte field

- [x] deterministic_double_run
- [x] distractors_distinct -- each wrong fix must differ from buggy_code, fixed_code, and the others

#### Semantic gate verdicts
(no semantic gate receipts for this type)
