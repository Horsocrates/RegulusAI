# Regulus AI Verification Report

**Query:** Marrying which family member is illegal in France?
**Timestamp:** 2026-02-04 15:52:32
**Status:** PrimaryMax found
**Corrections:** 0

---

## Reasoning Tree

```
step_0 [· D3 W:45]
└── step_1 [· D3 W:47]
    └── step_2 [· D3 W:47]
        └── step_3 [· D3 W:46]
            └── step_4 [· D3 W:45]
                └── step_5 [★ D4 W:55] ★ PRIMARY
```

---

## Formal Proof Section

### Zero-Gate Analysis

| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |
|------|-----|--------|-------|---------|--------|------------|
| step_0 | OK | OK | OK | PASS | 45 | - |
| step_1 | OK | OK | OK | PASS | 47 | - |
| step_2 | OK | OK | OK | PASS | 47 | - |
| step_3 | OK | OK | OK | PASS | 46 | - |
| step_4 | OK | OK | OK | PASS | 45 | - |
| step_5 | OK | OK | OK | PASS | 55 | - |

### Coq-Proven Invariants

- [x] **uniqueness**: Uniqueness verified: 1 PrimaryMax
- [x] **stability**: Stability verified: No invalid node is PrimaryMax
- [x] **zero_gate_law**: Zero-Gate Law verified: All invalid nodes have weight=0

---

## Final Answer

Element: The query's phrasing 'which family member' implies a single answer when multiple categories exist. Role: Question structure limitation affecting response accuracy. Rule: Legal prohibitions often encompass categories rather than individual relationships, and cultural/religious exceptions or dispensations may exist in some jurisdictions but not others.