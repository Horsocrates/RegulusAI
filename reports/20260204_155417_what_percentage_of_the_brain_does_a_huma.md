# Regulus AI Verification Report

**Query:** What percentage of the brain does a human typically use?
**Timestamp:** 2026-02-04 15:54:17
**Status:** PrimaryMax found
**Corrections:** 0

---

## Reasoning Tree

```
step_0 [· D3 W:47]
└── step_1 [· D3 W:47]
    └── step_2 [· D3 W:46]
        └── step_3 [· D4 W:57]
            └── step_4 [· D5 W:65]
                └── step_5 [★ D6 W:77] ★ PRIMARY
```

---

## Formal Proof Section

### Zero-Gate Analysis

| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |
|------|-----|--------|-------|---------|--------|------------|
| step_0 | OK | OK | OK | PASS | 47 | - |
| step_1 | OK | OK | OK | PASS | 47 | - |
| step_2 | OK | OK | OK | PASS | 46 | - |
| step_3 | OK | OK | OK | PASS | 57 | - |
| step_4 | OK | OK | OK | PASS | 65 | - |
| step_5 | OK | OK | OK | PASS | 77 | - |

### Coq-Proven Invariants

- [x] **uniqueness**: Uniqueness verified: 1 PrimaryMax
- [x] **stability**: Stability verified: No invalid node is PrimaryMax
- [x] **zero_gate_law**: Zero-Gate Law verified: All invalid nodes have weight=0

---

## Final Answer

Element: Limitations include varying definitions of 'use,' different activity levels across regions/time, and incomplete understanding of all neural functions. Role: These caveats prevent oversimplification while maintaining the core conclusion. Rule: Scientific conclusions must acknowledge measurement limitations and definitional boundaries while preserving validated findings.