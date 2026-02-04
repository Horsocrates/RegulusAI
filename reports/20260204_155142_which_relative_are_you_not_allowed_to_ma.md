# Regulus AI Verification Report

**Query:** Which relative are you not allowed to marry in California?
**Timestamp:** 2026-02-04 15:51:42
**Status:** PrimaryMax found
**Corrections:** 0

---

## Reasoning Tree

```
step_0 [· D2 W:35]
└── step_1 [· D3 W:47]
    └── step_2 [· D3 W:47]
        └── step_3 [· D3 W:47]
            └── step_4 [· D4 W:55]
                └── step_5 [★ D6 W:75] ★ PRIMARY
```

---

## Formal Proof Section

### Zero-Gate Analysis

| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |
|------|-----|--------|-------|---------|--------|------------|
| step_0 | OK | OK | OK | PASS | 35 | - |
| step_1 | OK | OK | OK | PASS | 47 | - |
| step_2 | OK | OK | OK | PASS | 47 | - |
| step_3 | OK | OK | OK | PASS | 47 | - |
| step_4 | OK | OK | OK | PASS | 55 | - |
| step_5 | OK | OK | OK | PASS | 75 | - |

### Coq-Proven Invariants

- [x] **uniqueness**: Uniqueness verified: 1 PrimaryMax
- [x] **stability**: Stability verified: No invalid node is PrimaryMax
- [x] **zero_gate_law**: Zero-Gate Law verified: All invalid nodes have weight=0

---

## Final Answer

Element: Response limitations include potential statutory changes, ceremonial vs. legal recognition distinctions, and jurisdictional variations. Role: Acknowledgment of legal complexity and temporal constraints. Rule: Legal advice requires current verification and may not cover all situational nuances.