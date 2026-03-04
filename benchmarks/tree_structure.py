#!/usr/bin/env python3
"""
Visualize the 156-fallacy classification tree with branching factors at each gate.

Shows:
  Gate 0: Binary (error or not)              -> 2 options
  Gate 1: Violation Type (type1-5)           -> 5 options
  Gate 2: Domain (D1-D6) or Sub-Type (T1A/B) -> 2-6 options
  Gate 3: Failure Mode (D1.1-D6.4)           -> 3-5 options
  Gate 4: Specific ID                        -> 1-10 options
"""

from __future__ import annotations
import sys, os
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from regulus.fallacies.taxonomy import FALLACIES, FallacyType, Domain, FailureMode


def main():
    # Build the tree
    tree = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    type_names = {
        FallacyType.T1_CONDITION_VIOLATION: "type1",
        FallacyType.T2_DOMAIN_VIOLATION: "type2",
        FallacyType.T3_SEQUENCE_VIOLATION: "type3",
        FallacyType.T4_SYNDROME: "type4",
        FallacyType.T5_CONTEXT_DEPENDENT: "type5",
    }

    domain_names = {
        Domain.D1_RECOGNITION: "D1",
        Domain.D2_CLARIFICATION: "D2",
        Domain.D3_FRAMEWORK: "D3",
        Domain.D4_COMPARISON: "D4",
        Domain.D5_INFERENCE: "D5",
        Domain.D6_REFLECTION: "D6",
        Domain.NONE: "—",
    }

    for fid, f in sorted(FALLACIES.items()):
        vtype = type_names.get(f.fallacy_type, "?")
        domain = domain_names.get(f.domain, "?")
        fm = f.failure_mode.value if f.failure_mode else "—"
        tree[vtype][domain][fm].append(fid)

    # Print the tree
    print("=" * 70)
    print("156-FALLACY CLASSIFICATION TREE — BRANCHING FACTORS AT EACH GATE")
    print("=" * 70)
    print()
    print("Gate 0: Binary -> {error, valid}  (2 options)")
    print(f"Gate 1: Type   -> {len(tree)} types")
    print()

    total_ids = 0
    gate_stats = {
        "gate1_options": len(tree),
        "gate2_max": 0,
        "gate3_max": 0,
        "gate4_max": 0,
    }

    for vtype in sorted(tree.keys()):
        domains = tree[vtype]
        type_count = sum(len(ids) for d in domains.values() for ids in d.values())
        print(f"+-- {vtype} ({type_count} fallacies) — Gate 2: {len(domains)} options")
        gate_stats["gate2_max"] = max(gate_stats["gate2_max"], len(domains))

        for domain in sorted(domains.keys()):
            fms = domains[domain]
            domain_count = sum(len(ids) for ids in fms.values())
            print(f"|   +-- {domain} ({domain_count}) — Gate 3: {len(fms)} options")
            gate_stats["gate3_max"] = max(gate_stats["gate3_max"], len(fms))

            for fm in sorted(fms.keys()):
                ids = fms[fm]
                total_ids += len(ids)
                gate_stats["gate4_max"] = max(gate_stats["gate4_max"], len(ids))

                if len(ids) <= 5:
                    id_str = ", ".join(ids)
                else:
                    id_str = ", ".join(ids[:3]) + f"... (+{len(ids)-3} more)"
                print(f"|   |   +-- {fm} ({len(ids)}) -> {id_str}")

        print("|")

    print()
    print("=" * 70)
    print("GATE SUMMARY — Maximum options at each gate")
    print("=" * 70)
    print(f"  Gate 0 (Binary):       2 options   — 'is there an error?'")
    print(f"  Gate 1 (Type):         {gate_stats['gate1_options']} options   — 'which type of violation?'")
    print(f"  Gate 2 (Domain):       {gate_stats['gate2_max']} options   — 'which domain?' (max)")
    print(f"  Gate 3 (Failure Mode): {gate_stats['gate3_max']} options   — 'what failure mode?' (max)")
    print(f"  Gate 4 (Specific ID):  {gate_stats['gate4_max']} options  — 'which specific fallacy?' (max)")
    print()
    print(f"  Total leaf IDs: {total_ids}")
    print()

    # Show the specific gate sequence for type2 (the hard case)
    print("=" * 70)
    print("TYPE 2 DEEP DIVE — Gate-by-gate options for the 105-fallacy type")
    print("=" * 70)
    print()
    if "type2" in tree:
        for domain in sorted(tree["type2"].keys()):
            fms = tree["type2"][domain]
            domain_count = sum(len(ids) for ids in fms.values())
            print(f"  {domain} ({domain_count} fallacies):")
            for fm in sorted(fms.keys()):
                ids = fms[fm]
                print(f"    {fm} ({len(ids)}): {', '.join(sorted(ids))}")
            print()

    # Compare: current cascade vs proposed multi-gate
    print("=" * 70)
    print("COMPARISON: Current vs Proposed Architecture")
    print("=" * 70)
    print()
    print("CURRENT CASCADE (2 calls):")
    print("  Call 1: Type (5 options)")
    print("  Call 2: Specific ID (3-105 options!)  <- bottleneck")
    print()
    print("PROPOSED MULTI-GATE (3-4 calls):")
    print("  Call 1: Type (5 options)")
    print("  Call 2: Domain (2-7 options)")
    print("  Call 3: Failure Mode (1-5 options)")
    print("  Call 4: Specific ID (1-10 options)  <- easy choice!")
    print()
    print("Key insight: max branching factor drops from 105 -> 10")
    print()

    # For type2, show what each gate sequence looks like
    print("EXAMPLE GATE SEQUENCES:")
    examples = [
        ("D1_AD_HOMINEM", "Ad hominem attack"),
        ("D5_POST_HOC", "False cause"),
        ("T1B_SCARE_TACTICS", "Fear manipulation"),
        ("T3_CIRCULAR_REASONING", "Circular argument"),
    ]
    for fid, desc in examples:
        f = FALLACIES.get(fid)
        if f:
            vtype = type_names.get(f.fallacy_type, "?")
            domain = domain_names.get(f.domain, "?")
            fm = f.failure_mode.value if f.failure_mode else "—"
            print(f"  {desc}:")
            print(f"    Gate1:{vtype} -> Gate2:{domain} -> Gate3:{fm} -> Gate4:{fid}")
    print()


if __name__ == "__main__":
    main()
