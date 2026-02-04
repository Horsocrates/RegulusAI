# Regulus AI Verification Report

**Query:** It is illegal to drive in the UK if you are wearing what?
**Timestamp:** 2026-02-04 15:50:55
**Status:** PrimaryMax found
**Corrections:** 0

---

## Reasoning Tree

```
step_0 [· D2 W:35]
└── step_1 [· D3 W:47]
    └── step_2 [· D3 W:47]
        └── step_3 [· D4 W:55]
            └── step_4 [· D5 W:65]
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
| step_3 | OK | OK | OK | PASS | 55 | - |
| step_4 | OK | OK | OK | PASS | 65 | - |
| step_5 | OK | OK | OK | PASS | 75 | - |

### Coq-Proven Invariants

- [x] **uniqueness**: Uniqueness verified: 1 PrimaryMax
- [x] **stability**: Stability verified: No invalid node is PrimaryMax
- [x] **zero_gate_law**: Zero-Gate Law verified: All invalid nodes have weight=0

---

## Final Answer

Element: This conclusion may not account for specific circumstances or indirect legal implications. Role: Limitation acknowledging potential edge cases. Rule: Clothing that impairs driving ability could still result in charges under dangerous/careless driving laws, even without explicit prohibition.