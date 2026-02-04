# Regulus AI Verification Report

**Query:** What happens if you wake a sleepwalker?
**Timestamp:** 2026-02-04 15:43:57
**Status:** PrimaryMax found
**Corrections:** 3

---

## Reasoning Tree

```
step_0 [· D3 W:45]
└── step_1 [· D3 W:45]
    └── step_2 [· D3 W:45]
        └── step_3 [· D4 W:55]
            └── step_4 [★ D5 W:65] ★ PRIMARY
                └── step_5 [✗ ORDER]
```

---

## Formal Proof Section

### Zero-Gate Analysis

| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |
|------|-----|--------|-------|---------|--------|------------|
| step_0 | OK | OK | OK | PASS | 45 | - |
| step_1 | OK | OK | OK | PASS | 45 | - |
| step_2 | OK | OK | OK | PASS | 45 | - |
| step_3 | OK | OK | OK | PASS | 55 | - |
| step_4 | OK | OK | OK | PASS | 65 | - |
| step_5 | OK | OK | FAIL | FAIL | 0 | ORDER_D6 |

### Coq-Proven Invariants

- [x] **uniqueness**: Uniqueness verified: 1 PrimaryMax
- [x] **stability**: Stability verified: No invalid node is PrimaryMax
- [x] **zero_gate_law**: Zero-Gate Law verified: All invalid nodes have weight=0

---

## Corrections Log

| Step | Attempt | Code | Result |
|------|---------|------|--------|
| 5 | 1 | ORDER_D6 | FAIL |
| 5 | 2 | ORDER_D6 | FAIL |
| 5 | 3 | ORDER_D6 | FAIL |

---

## Final Answer

Element: Waking a sleepwalker is generally safe but may cause temporary confusion and disorientation. Role: The main consideration should be preventing injury during the confused awakening period rather than avoiding awakening altogether. Rule: Gentle guidance back to bed is often preferable to abrupt awakening, but awakening itself poses no serious medical risk.