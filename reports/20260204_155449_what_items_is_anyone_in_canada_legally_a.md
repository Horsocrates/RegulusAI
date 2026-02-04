# Regulus AI Verification Report

**Query:** What items is anyone in Canada legally allowed to carry?
**Timestamp:** 2026-02-04 15:54:49
**Status:** PrimaryMax found
**Corrections:** 0

---

## Reasoning Tree

```
step_0 [· D1 W:25]
└── step_1 [· D2 W:37]
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
| step_1 | OK | OK | OK | PASS | 37 | - |
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

Element: Canadian legal framework operates through federal criminal law, provincial regulation, and municipal authority. Role: Provides systematic structure for evaluating carry permissions. Rule: Items are permissible unless specifically prohibited, with federal law superseding provincial/municipal where applicable.