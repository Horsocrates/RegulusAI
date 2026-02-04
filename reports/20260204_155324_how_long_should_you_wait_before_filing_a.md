# Regulus AI Verification Report

**Query:** How long should you wait before filing a missing person report?
**Timestamp:** 2026-02-04 15:53:24
**Status:** PrimaryMax found
**Corrections:** 0

---

## Reasoning Tree

```
step_0 [· D1 W:25]
└── step_1 [· D2 W:37]
    └── step_2 [· D3 W:46]
        └── step_3 [· D4 W:55]
            └── step_4 [· D5 W:65]
                └── step_5 [★ D6 W:75] ★ PRIMARY
```

---

## Formal Proof Section

### Zero-Gate Analysis

| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |
|------|-----|--------|-------|---------|--------|------------|
| step_0 | OK | OK | OK | PASS | 25 | - |
| step_1 | OK | OK | OK | PASS | 37 | - |
| step_2 | OK | OK | OK | PASS | 46 | - |
| step_3 | OK | OK | OK | PASS | 55 | - |
| step_4 | OK | OK | OK | PASS | 65 | - |
| step_5 | OK | OK | OK | PASS | 75 | - |

### Coq-Proven Invariants

- [x] **uniqueness**: Uniqueness verified: 1 PrimaryMax
- [x] **stability**: Stability verified: No invalid node is PrimaryMax
- [x] **zero_gate_law**: Zero-Gate Law verified: All invalid nodes have weight=0

---

## Final Answer

Element: Limitations include jurisdictional variations and resource constraints affecting response priorities. Role: Acknowledgment of system boundaries and practical constraints. Rule: Reflection must recognize that while reports can be filed immediately, actual investigative response depends on assessed risk level and available resources.