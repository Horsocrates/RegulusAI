# Regulus AI Verification Report

**Query:** Who are you not allowed to marry in the UK?
**Timestamp:** 2026-02-04 15:51:20
**Status:** PrimaryMax found
**Corrections:** 0

---

## Reasoning Tree

```
step_0 [· D1 W:25]
└── step_1 [· D2 W:35]
    └── step_2 [· D3 W:47]
        └── step_3 [· D3 W:47]
            └── step_4 [· D3 W:45]
                └── step_5 [★ D6 W:75] ★ PRIMARY
```

---

## Formal Proof Section

### Zero-Gate Analysis

| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |
|------|-----|--------|-------|---------|--------|------------|
| step_0 | OK | OK | OK | PASS | 25 | - |
| step_1 | OK | OK | OK | PASS | 35 | - |
| step_2 | OK | OK | OK | PASS | 47 | - |
| step_3 | OK | OK | OK | PASS | 47 | - |
| step_4 | OK | OK | OK | PASS | 45 | - |
| step_5 | OK | OK | OK | PASS | 75 | - |

### Coq-Proven Invariants

- [x] **uniqueness**: Uniqueness verified: 1 PrimaryMax
- [x] **stability**: Stability verified: No invalid node is PrimaryMax
- [x] **zero_gate_law**: Zero-Gate Law verified: All invalid nodes have weight=0

---

## Final Answer

Element: This analysis covers general UK law but doesn't account for religious marriage restrictions, international complications, or recent legislative changes. Role: These limitations acknowledge gaps in the comprehensive coverage of marriage restrictions. Rule: Legal analysis must acknowledge scope limitations and temporal constraints.