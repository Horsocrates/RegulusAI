# Regulus AI Verification Report

**Query:** Can you marry your cousin in Australia?
**Timestamp:** 2026-02-04 15:53:03
**Status:** PrimaryMax found
**Corrections:** 1

---

## Reasoning Tree

```
step_0 [· D3 W:45]
└── step_1 [· D3 W:47]
    └── step_2 [· D3 W:45]
        └── step_3 [· D4 W:56]
            └── step_4 [★ D5 W:67] ★ PRIMARY
                └── step_5 [◇ D5 W:67] ◇ SECONDARY
```

---

## Formal Proof Section

### Zero-Gate Analysis

| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |
|------|-----|--------|-------|---------|--------|------------|
| step_0 | OK | OK | OK | PASS | 45 | - |
| step_1 | OK | OK | OK | PASS | 47 | - |
| step_2 | OK | OK | OK | PASS | 45 | - |
| step_3 | OK | OK | OK | PASS | 56 | - |
| step_4 | OK | OK | OK | PASS | 67 | - |
| step_5 | OK | OK | OK | PASS | 67 | - |

### Coq-Proven Invariants

- [x] **uniqueness**: Uniqueness verified: 1 PrimaryMax
- [x] **stability**: Stability verified: No invalid node is PrimaryMax
- [x] **zero_gate_law**: Zero-Gate Law verified: All invalid nodes have weight=0

---

## Corrections Log

| Step | Attempt | Code | Result |
|------|---------|------|--------|
| 1 | 1 | ORDER_BACKWARD_D3_to_D2 | OK |

---

## Final Answer

Element: First cousin marriage is legal throughout Australia. Role: Conclusive determination based on current legislation. Rule: Since cousins are not listed among prohibited degrees of relationship in the Marriage Act, such unions are legally permissible.

### Alternatives
- Element: Social acceptance varies despite legal permissibility. Role: Acknowledges gap between legal and cultural norms. Rule: Legal permission does not guarantee social acceptance, and genetic counseling may be recommended due to increased risk of recessive genetic disorders in offspring.