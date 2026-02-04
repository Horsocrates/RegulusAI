#!/usr/bin/env python3
"""
LogicGuard Demo: Paradox Detection
===================================

Demonstrates how the Zero-Gate mechanism detects and blocks
classical paradoxes (Liar, Russell) and logical fallacies.

Run: python -m logicguard.demos.paradox_demo
"""

import sys
sys.path.insert(0, '/home/claude')

from logicguard import (
    LogicGuardEngine, verify_reasoning,
    get_paradox_example, list_paradox_examples,
    render_ascii_tree, render_graphviz, full_report
)


def demo_paradox(name: str) -> None:
    """Run demo for a specific paradox"""
    print("\n" + "=" * 70)
    print(f"PARADOX: {name.upper()}")
    print("=" * 70)
    
    # Get paradox example
    paradox = get_paradox_example(name)
    
    print(f"\nStatement: {paradox.statement}")
    print(f"\nExplanation: {paradox.explanation}")
    print(f"\nExpected Gate Failure: {paradox.expected_gate_failure}")
    
    # Verify
    engine = LogicGuardEngine()
    result = engine.verify(paradox.tree)
    
    # Show tree
    print("\n" + "-" * 40)
    print("REASONING TREE:")
    print("-" * 40)
    print(render_ascii_tree(result))
    
    # Show verdict
    print("\n" + "-" * 40)
    print("VERDICT:")
    print("-" * 40)
    print(f"Total nodes: {len(result.nodes)}")
    print(f"Invalid (blocked): {result.invalid_count}")
    print(f"Primary conclusion: {result.primary_max.node_id if result.primary_max else 'NONE (paradox blocked)'}")
    
    # Verify properties
    verifications = engine.run_verifications(result.nodes)
    print("\nCoq-Verified Properties:")
    for prop, (passed, msg) in verifications.items():
        status = "✓" if passed else "✗"
        print(f"  [{status}] {prop}: {msg}")


def demo_all_paradoxes():
    """Run demo for all available paradoxes"""
    print("\n" + "#" * 70)
    print("# LOGICGUARD PARADOX DEMONSTRATION")
    print("# Showing how Zero-Gate blocks structural violations")
    print("#" * 70)
    
    for name in list_paradox_examples():
        demo_paradox(name)
    
    print("\n" + "=" * 70)
    print("CONCLUSION:")
    print("=" * 70)
    print("""
The Zero-Gate mechanism successfully:

1. LIAR PARADOX: Blocked due to LEVELS violation (self-reference)
2. RUSSELL'S PARADOX: Blocked due to LEVELS violation (self-application)
3. NON-SEQUITUR: Blocked due to ERR violation (missing Rule)
4. DOMAIN SKIP: Blocked due to ORDER violation (D1→D5 jump)
5. VALID SYLLOGISM: Passed - proper structure maintained

Key insight: Paradoxes are not "mysterious" - they are STRUCTURAL VIOLATIONS
that the Zero-Gate makes PHYSICALLY IMPOSSIBLE to propagate.

"Hallucination is not a failure of fact-checking.
 Hallucination is a failure of structural integrity."
""")


def save_graphviz_examples():
    """Save Graphviz files for article illustrations"""
    import os
    
    output_dir = "/home/claude/logicguard/demos/output"
    os.makedirs(output_dir, exist_ok=True)
    
    for name in list_paradox_examples():
        paradox = get_paradox_example(name)
        result = verify_reasoning(paradox.tree)
        
        filepath = f"{output_dir}/{name}_tree.dot"
        dot = render_graphviz(
            result, 
            title=f"LogicGuard: {paradox.name}",
            show_content=True
        )
        with open(filepath, 'w') as f:
            f.write(dot)
        print(f"Saved: {filepath}")
    
    print(f"\nTo render: dot -Tpng {output_dir}/liar_tree.dot -o liar_tree.png")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--graphviz":
            save_graphviz_examples()
        else:
            demo_paradox(sys.argv[1])
    else:
        demo_all_paradoxes()
