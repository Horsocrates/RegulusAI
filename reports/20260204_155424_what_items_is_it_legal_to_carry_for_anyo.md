# Regulus AI Verification Report

**Query:** What items is it legal to carry for anyone in the US?
**Timestamp:** 2026-02-04 15:54:24
**Status:** PrimaryMax found
**Corrections:** 0

---

## Reasoning Tree

```
step_0 [· D1 W:25]
└── step_1 [· D2 W:36]
    └── step_2 [★ D3 W:47] ★ PRIMARY
        └── step_3 [· D3 W:45]
            └── step_4 [· D3 W:45]
                └── step_5 [· D3 W:45]
```

---

## Formal Proof Section

### Zero-Gate Analysis

| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |
|------|-----|--------|-------|---------|--------|------------|
| step_0 | OK | OK | OK | PASS | 25 | - |
| step_1 | OK | OK | OK | PASS | 36 | - |
| step_2 | OK | OK | OK | PASS | 47 | - |
| step_3 | OK | OK | OK | PASS | 45 | - |
| step_4 | OK | OK | OK | PASS | 45 | - |
| step_5 | OK | OK | OK | PASS | 45 | - |

### Coq-Proven Invariants

- [x] **uniqueness**: Uniqueness verified: 1 PrimaryMax
- [x] **stability**: Stability verified: No invalid node is PrimaryMax
- [x] **zero_gate_law**: Zero-Gate Law verified: All invalid nodes have weight=0

---

## Final Answer

Element: US federalism framework with constitutional protections and jurisdictional layers. Role: Evaluation requires analyzing items through federal constitutional rights, state police powers, and local ordinances. Rule: Legal analysis must account for the hierarchy of federal constitution > federal law > state law > local law.