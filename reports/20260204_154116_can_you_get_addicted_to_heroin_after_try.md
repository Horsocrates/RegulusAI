# Regulus AI Verification Report

**Query:** Can you get addicted to heroin after trying it once?
**Timestamp:** 2026-02-04 15:41:16
**Status:** PrimaryMax found
**Corrections:** 0

---

## Reasoning Tree

```
step_0 [· D3 W:46]
└── step_1 [· D3 W:47]
    └── step_2 [· D3 W:47]
        └── step_3 [· D4 W:55]
            └── step_4 [★ D5 W:67] ★ PRIMARY
                └── step_5 [◇ D5 W:67] ◇ SECONDARY
```

---

## Formal Proof Section

### Zero-Gate Analysis

| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |
|------|-----|--------|-------|---------|--------|------------|
| step_0 | OK | OK | OK | PASS | 46 | - |
| step_1 | OK | OK | OK | PASS | 47 | - |
| step_2 | OK | OK | OK | PASS | 47 | - |
| step_3 | OK | OK | OK | PASS | 55 | - |
| step_4 | OK | OK | OK | PASS | 67 | - |
| step_5 | OK | OK | OK | PASS | 67 | - |

### Coq-Proven Invariants

- [x] **uniqueness**: Uniqueness verified: 1 PrimaryMax
- [x] **stability**: Stability verified: No invalid node is PrimaryMax
- [x] **zero_gate_law**: Zero-Gate Law verified: All invalid nodes have weight=0

---

## Final Answer

Element: Conclusion that true addiction cannot occur from single use, though high risk exists. Role: Evidence-based assessment acknowledging both the scientific definition and practical dangers. Rule: Single exposure can create strong psychological desire and physical effects, but addiction as clinically defined requires repeated use establishing compulsive patterns.

### Alternatives
- Element: Individual variation in genetic predisposition, mental health status, and environmental factors. Role: Acknowledging that addiction risk varies significantly between individuals. Rule: While single-use addiction is clinically inaccurate, some individuals may progress extremely rapidly to compulsive use, making the distinction practically dangerous for harm reduction messaging.