#!/usr/bin/env python3
"""
Canonical Classification Tree from Horsokrates (2026).

Source: "The Architecture of Error" (Article 4) + "Domain Violations" (Article 5)
Published: philpapers.org/archive/HORTAO-17.pdf, philpapers.org/archive/HORDVA.pdf

The Diagnostic Algorithm (Article 4, Section 2.4):
  Step 1: Did reasoning begin? If not -> Type 1
  Step 2: In which domain did failure occur? -> Type 2
  Step 3: Was sequence violated? -> Type 3
  Step 4: Is this systemic? -> Type 4
  Step 5: Is the method context-dependent? -> Type 5

This gives us the GATE STRUCTURE for classification:
  Gate 0: Binary (is there a violation?)
  Gate 1: Which type? (5 options)
  Gate 2: Sub-classification within type (2-10 options)
  Gate 3: Failure mode (1-5 options)
  Gate 4: Specific fallacy ID (1-16 options)
"""

import sys, os
sys.stdout.reconfigure(encoding='utf-8')

# =========================================================================
# CANONICAL TREE FROM PAPERS
# =========================================================================

CANONICAL_TREE = {
    "type1": {
        "name": "Violation of Conditions",
        "count": 36,
        "gate_question": "Did reasoning begin? Or was it replaced by manipulation?",
        "subtypes": {
            "T1A": {
                "name": "Defective Questions",
                "count": 3,
                "gate_question": "Is the question itself defective?",
                "fallacies": [
                    "T1A_COMPLEX_QUESTION",   # 1.1.1 Loaded Question
                    "T1A_TABOO",              # 1.1.2 Exclusion of Topics
                    "T1A_VENUE_FALLACY",      # 1.1.3 Exclusion by Context
                ],
            },
            "T1B": {
                "name": "Manipulations",
                "count": 33,
                "gate_question": "What type of manipulation replaces argument?",
                "categories": {
                    "1.2.1 Force": {
                        "count": 8,
                        "gate_question": "Is force/threat used instead of argument?",
                        "fallacies": [
                            "T1B_AD_BACULUM",          # Threat
                            "T1B_JUST_DO_IT",          # Command without justification
                            "T1B_NO_DISCUSSION",       # Foreclosing debate
                            "T1B_PLAUSIBLE_DENIABILITY",# Deniable threat
                            "T1B_THE_POUT",            # Emotional punishment
                            "T1B_STANDARD_VERSION",    # "How we do things"
                            "T1B_THOUSAND_FLOWERS",    # False invitation to critique
                            "T1B_TINA",                # There Is No Alternative
                        ],
                    },
                    "1.2.2 Pity": {
                        "count": 3,
                        "gate_question": "Is pity/sympathy used instead of argument?",
                        "fallacies": [
                            "T1B_APPEAL_TO_PITY",      # Compassion as grounds
                            "T1B_NARRATIVE_FALLACY",   # Compelling story as evidence
                            "T1B_SAVE_THE_CHILDREN",   # Vulnerable groups to foreclose analysis
                        ],
                    },
                    "1.2.3 Emotion": {
                        "count": 7,
                        "gate_question": "Is emotion used to bypass reasoning?",
                        "fallacies": [
                            "T1B_SCARE_TACTICS",       # Fear
                            "T1B_DOG_WHISTLE",         # Coded emotional language
                            "T1B_F_BOMB",              # Shock value
                            "T1B_PLAYING_ON_EMOTION",  # Sob story
                            "T1B_PROSOPOLOGY",         # Emotional repetition
                            "T1B_SHOPPING_HUNGRY",     # Decisions in aroused state
                            "T1B_WE_HAVE_TO_DO_SOMETHING",  # Action bias
                        ],
                    },
                    "1.2.4 Benefit": {
                        "count": 1,
                        "gate_question": "Is benefit/bribery offered instead of argument?",
                        "fallacies": ["T1B_BRIBERY"],
                    },
                    "1.2.5 Pressure": {
                        "count": 1,
                        "gate_question": "Is social pressure used instead of argument?",
                        "fallacies": ["T1B_APPEASEMENT"],
                    },
                    "1.2.6 False Authority": {
                        "count": 3,
                        "gate_question": "Is irrelevant authority cited?",
                        "fallacies": [
                            "T1B_APPEAL_TO_HEAVEN",    # Divine/unverifiable authority
                            "T1B_AD_MYSTERIAM",        # Mystery as authority
                            "T1B_PSEUDO_ESOTERIC",     # Secret knowledge
                        ],
                    },
                    "1.2.7 Disinformation": {
                        "count": 5,
                        "gate_question": "Is truth itself being attacked?",
                        "fallacies": [
                            "T1B_BIG_LIE",             # Audacious falsehood
                            "T1B_ALTERNATIVE_TRUTH",   # Fabrication as perspective
                            "T1B_GASLIGHTING",         # Denial of reality
                            "T1B_INFOTAINMENT",        # Blurring news/entertainment
                            "T1B_SCRIPTED_MESSAGE",    # Coordinated repetition
                        ],
                    },
                    "1.2.8 Delegation": {
                        "count": 2,
                        "gate_question": "Is reasoning delegated/abdicated?",
                        "fallacies": [
                            "T1B_BLIND_LOYALTY",       # Submission to authority
                            "T1B_BIG_BRAIN_LITTLE_BRAIN",  # Deference without evaluation
                        ],
                    },
                    "1.2.9 False Ethos": {
                        "count": 1,
                        "gate_question": "Is expertise faked through form?",
                        "fallacies": ["T1B_ALPHABET_SOUP"],
                    },
                    "1.2.10 Bad Faith": {
                        "count": 2,
                        "gate_question": "Is the speaker arguing in bad faith?",
                        "fallacies": [
                            "T1B_MALA_FIDES",          # Knowing violation of norms
                            "T1B_OCTOBER_SURPRISE",    # Strategic timing
                        ],
                    },
                },
            },
        },
    },

    "type2": {
        "name": "Domain Violations",
        "count": 105,
        "gate_question": "In which domain did reasoning fail?",
        "domains": {
            "D1": {
                "name": "Recognition",
                "function": "Fixation of what is present",
                "err": "Element (WHAT)",
                "count": 26,
                "gate_question": "Was the object of reasoning correctly recognized?",
                "failure_modes": {
                    "D1.1": {
                        "name": "Object Deformation (A->A')",
                        "count": 2,
                        "gate_question": "Was the real claim distorted/exaggerated?",
                        "fallacies": ["D1_STRAW_MAN", "D1_RED_HERRING"],
                    },
                    "D1.2": {
                        "name": "Object Substitution (A->B)",
                        "count": 16,
                        "gate_question": "Was the argument replaced by something else (person, topic)?",
                        "fallacies": [
                            "D1_AD_HOMINEM", "D1_ARGUMENT_FROM_MOTIVES",
                            "D1_BLOOD_IS_THICKER", "D1_GUILT_BY_ASSOCIATION",
                            "D1_IDENTITY_FALLACY", "D1_JUST_PLAIN_FOLKS",
                            "D1_NAME_CALLING", "D1_OLFACTORY_RHETORIC",
                            "D1_OTHERING", "D1_PATERNALISM",
                            "D1_REDUCTIO_AD_HITLERUM", "D1_ROMANTIC_REBEL",
                            "D1_STAR_POWER", "D1_TONE_POLICING",
                            "D1_TRANSFER", "D1_TU_QUOQUE",
                        ],
                    },
                    "D1.3": {
                        "name": "Data Filtration",
                        "count": 5,
                        "gate_question": "Was evidence selectively presented?",
                        "fallacies": [
                            "D1_AVAILABILITY_BIAS", "D1_DISCIPLINARY_BLINDERS",
                            "D1_HALF_TRUTH", "D1_LYING_WITH_STATISTICS", "D1_NIMBY",
                        ],
                    },
                    "D1.4": {
                        "name": "Projection",
                        "count": 2,
                        "gate_question": "Were internal biases imposed on reality?",
                        "fallacies": ["D1_MIND_READING", "D1_POLLYANNA"],
                    },
                    "D1.5": {
                        "name": "Source Distortion",
                        "count": 1,
                        "gate_question": "Was the information source corrupted?",
                        "fallacies": ["D1_BRAINWASHING"],
                    },
                },
            },
            "D2": {
                "name": "Clarification",
                "function": "Understanding of what was recognized",
                "err": "Role (HOW)",
                "count": 13,
                "gate_question": "Were terms and meanings handled correctly?",
                "failure_modes": {
                    "D2.1": {
                        "name": "Meaning Drift",
                        "count": 7,
                        "gate_question": "Did a key term change meaning during the argument?",
                        "fallacies": [
                            "D2_EQUIVOCATION", "D2_ETYMOLOGICAL", "D2_REIFICATION",
                            "D2_POLITICAL_CORRECTNESS", "D2_HEROES_ALL",
                            "D2_ACTIONS_CONSEQUENCES", "D2_DIMINISHED_RESPONSIBILITY",
                        ],
                    },
                    "D2.2": {
                        "name": "Hidden Agent",
                        "count": 1,
                        "gate_question": "Was human agency concealed?",
                        "fallacies": ["D2_PASSIVE_VOICE"],
                    },
                    "D2.3": {
                        "name": "Incomplete Analysis",
                        "count": 3,
                        "gate_question": "Were options artificially limited?",
                        "fallacies": ["D2_EITHER_OR", "D2_PLAIN_TRUTH", "D2_REDUCTIONISM"],
                    },
                    "D2.4": {
                        "name": "Excessive Analysis",
                        "count": 2,
                        "gate_question": "Was analysis excessive, creating confusion?",
                        "fallacies": ["D2_OVEREXPLANATION", "D2_SNOW_JOB"],
                    },
                },
            },
            "D3": {
                "name": "Framework Selection",
                "function": "Determination of evaluative criteria",
                "err": "Rule (WHY/connection)",
                "count": 16,
                "gate_question": "Was the evaluative framework appropriate?",
                "failure_modes": {
                    "D3.1": {
                        "name": "Category Mismatch",
                        "count": 3,
                        "gate_question": "Was the wrong TYPE of framework applied?",
                        "fallacies": ["D3_ESCHATOLOGICAL", "D3_MEASURABILITY", "D3_PROCRUSTEAN"],
                    },
                    "D3.2": {
                        "name": "Irrelevant Criterion",
                        "count": 9,
                        "gate_question": "Was an irrelevant criterion used (popularity, tradition, emotion)?",
                        "fallacies": [
                            "D3_ABLEISM", "D3_AFFECTIVE", "D3_APPEAL_TO_NATURE",
                            "D3_APPEAL_TO_TRADITION", "D3_BANDWAGON", "D3_COST_BIAS",
                            "D3_E_FOR_EFFORT", "D3_MORTIFICATION", "D3_SOLDIERS_HONOR",
                        ],
                    },
                    "D3.3": {
                        "name": "Framework for Result",
                        "count": 4,
                        "gate_question": "Was the framework chosen to get a predetermined result?",
                        "fallacies": [
                            "D3_BIG_BUT", "D3_MORAL_LICENSING",
                            "D3_MORAL_SUPERIORITY", "D3_MOVING_GOALPOSTS",
                        ],
                    },
                },
            },
            "D4": {
                "name": "Comparison",
                "function": "Application of framework to material",
                "err": "Element (WHAT is compared)",
                "count": 8,
                "gate_question": "Was the comparison legitimate?",
                "failure_modes": {
                    "D4.1": {
                        "name": "False Equation",
                        "count": 4,
                        "gate_question": "Were unequal things treated as equal?",
                        "fallacies": [
                            "D4_FALSE_ANALOGY", "D4_SCORING_FALLACY",
                            "D4_SIMPLETONS", "D4_TWO_SIDES",
                        ],
                    },
                    "D4.2": {
                        "name": "Unstable Criteria",
                        "count": 3,
                        "gate_question": "Did comparison criteria shift mid-argument?",
                        "fallacies": [
                            "D4_DOUBLE_STANDARD", "D4_FUNDAMENTAL_ATTRIBUTION",
                            "D4_WORST_NEGATES_BAD",
                        ],
                    },
                    "D4.3": {
                        "name": "Comparison with Nonexistent",
                        "count": 1,
                        "gate_question": "Was comparison made to an impossible ideal?",
                        "fallacies": ["D4_HERO_BUSTING"],
                    },
                },
            },
            "D5": {
                "name": "Inference",
                "function": "Extraction of what follows",
                "err": "Rule (logical derivation)",
                "count": 20,
                "gate_question": "Does the conclusion follow from the premises?",
                "failure_modes": {
                    "D5.1": {
                        "name": "Logical Gap",
                        "count": 1,
                        "gate_question": "Is there ANY logical connection between premises and conclusion?",
                        "fallacies": ["D5_NON_SEQUITUR"],
                    },
                    "D5.2": {
                        "name": "Causal Error",
                        "count": 7,
                        "gate_question": "Is causation misidentified?",
                        "fallacies": [
                            "D5_POST_HOC", "D5_MAGICAL_THINKING", "D5_PERSONALIZATION",
                            "D5_POSITIVE_THINKING", "D5_SCAPEGOATING",
                            "D5_JOBS_COMFORTER", "D5_TRUST_YOUR_GUT",
                        ],
                    },
                    "D5.3": {
                        "name": "Chain Error",
                        "count": 2,
                        "gate_question": "Does a chain of reasoning break at some link?",
                        "fallacies": ["D5_SLIPPERY_SLOPE", "D5_EXCLUDED_MIDDLE"],
                    },
                    "D5.4": {
                        "name": "Scale Error",
                        "count": 10,
                        "gate_question": "Does the conclusion exceed what the evidence supports?",
                        "fallacies": [
                            "D5_OVERGENERALIZATION", "D5_ARGUMENT_FROM_CONSEQUENCES",
                            "D5_ARGUMENT_FROM_IGNORANCE", "D5_ARGUMENT_FROM_SILENCE",
                            "D5_DRAW_OWN_CONCLUSION", "D5_HOYLES_FALLACY",
                            "D5_SILENT_MAJORITY", "D5_WHERES_SMOKE",
                            "D5_WISDOM_OF_CROWD", "D5_WORST_CASE",
                        ],
                    },
                },
            },
            "D6": {
                "name": "Reflection",
                "function": "Recognition of limits and revision",
                "err": "Rule (self-assessment)",
                "count": 22,
                "gate_question": "Are limits properly acknowledged?",
                "failure_modes": {
                    "D6.1": {
                        "name": "Illusion of Completion",
                        "count": 6,
                        "gate_question": "Is the conclusion treated as final when it shouldn't be?",
                        "fallacies": [
                            "D6_APPEAL_TO_CLOSURE", "D6_DEFAULT_BIAS",
                            "D6_ESSENTIALIZING", "D6_UNINTENDED_CONSEQUENCES",
                            "D6_NOTHING_NEW", "D6_PARALYSIS_OF_ANALYSIS",
                        ],
                    },
                    "D6.2": {
                        "name": "Self-Assessment Distortion",
                        "count": 2,
                        "gate_question": "Is one's own competence misjudged?",
                        "fallacies": ["D6_DUNNING_KRUGER", "D6_SUNK_COST"],
                    },
                    "D6.3": {
                        "name": "Past Investment",
                        "count": 2,
                        "gate_question": "Does past investment prevent needed revision?",
                        "fallacies": ["D6_ARGUMENT_FROM_INERTIA", "D6_DEFENSIVENESS"],
                    },
                    "D6.4": {
                        "name": "Immunization from Testing",
                        "count": 12,
                        "gate_question": "Is the conclusion protected from disconfirmation?",
                        "fallacies": [
                            "D6_ARGUMENT_FROM_INCREDULITY", "D6_CALLING_CARDS",
                            "D6_DELIBERATE_IGNORANCE", "D6_FINISH_THE_JOB",
                            "D6_FREE_SPEECH", "D6_MAGIC_WAND",
                            "D6_MYOB", "D6_NON_RECOGNITION",
                            "D6_WRONG_MESSAGE", "D6_ALL_CROOKS",
                            "D6_THIRD_PERSON_EFFECT", "D6_VENTING",
                        ],
                    },
                },
            },
        },
    },

    "type3": {
        "name": "Violation of Sequence",
        "count": 3,
        "gate_question": "Is reasoning going in the wrong direction (backward, circular)?",
        "fallacies": [
            "T3_RATIONALIZATION",       # Conclusion before premises
            "T3_CIRCULAR_REASONING",    # No real progression
            "T3_BURDEN_SHIFTING",       # Argumentative roles inverted
        ],
    },

    "type4": {
        "name": "Syndromes",
        "count": 6,
        "gate_question": "Is there a self-reinforcing cross-domain pattern?",
        "fallacies": [
            "T4_CONFIRMATION_BIAS",     # Seek only confirming evidence
            "T4_ECHO_CHAMBER",          # Closed information environment
            "T4_GROUPTHINK",            # Group pressure suppresses dissent
            "T4_COGNITIVE_CLOSURE",     # Need for answer overrides accuracy
            "T4_COMPARTMENTALIZATION",  # Contradictory beliefs held separately
            "T4_MOTIVATED_REASONING",   # Reasoning serves emotional needs
        ],
    },

    "type5": {
        "name": "Context-Dependent Methods",
        "count": 6,
        "gate_question": "Is this method valid or fallacious in this specific context?",
        "fallacies": [
            "T5_APPEAL_TRADITION_CONTEXT",     # Valid when tradition encodes wisdom
            "T5_APPEAL_NATURE_CONTEXT",        # Valid for biological contexts
            "T5_AFFECTIVE_REASONING",          # Valid in emotional domains
            "T5_TRUST_GUT_CONTEXT",            # Valid for experienced practitioners
            "T5_ARGUMENT_CONSEQUENCES_CONTEXT", # Valid for policy evaluation
            "T5_ARGUMENT_SILENCE_CONTEXT",     # Valid for document analysis
        ],
    },
}


def print_tree():
    """Print the canonical tree with gate questions at each level."""
    print("=" * 78)
    print("CANONICAL CLASSIFICATION TREE (Horsokrates 2026)")
    print("Source: Articles 4 & 5 from philpapers.org")
    print("=" * 78)
    print()
    print("DIAGNOSTIC ALGORITHM (Article 4, Section 2.4):")
    print("  Gate 0: Is there a violation?  [Binary]")
    print("  Gate 1: What type?             [5 options]")
    print("  Gate 2: Sub-classification     [2-10 options depending on type]")
    print("  Gate 3: Failure mode           [1-5 options]")
    print("  Gate 4: Specific fallacy ID    [1-16 options]")
    print()

    total = 0
    max_gate2 = 0
    max_gate3 = 0
    max_gate4 = 0

    for vtype, info in CANONICAL_TREE.items():
        count = info["count"]
        total += count
        print(f"[Gate 1] {vtype}: {info['name']} ({count})")
        print(f"  Q: \"{info['gate_question']}\"")

        if "subtypes" in info:
            # Type 1: T1A/T1B split
            subtypes = info["subtypes"]
            max_gate2 = max(max_gate2, len(subtypes))
            for st_key, st_info in subtypes.items():
                print(f"  [Gate 2] {st_key}: {st_info['name']} ({st_info['count']})")
                print(f"    Q: \"{st_info['gate_question']}\"")

                if "fallacies" in st_info:
                    max_gate4 = max(max_gate4, len(st_info["fallacies"]))
                    for f in st_info["fallacies"]:
                        print(f"      -> {f}")

                if "categories" in st_info:
                    cats = st_info["categories"]
                    max_gate3 = max(max_gate3, len(cats))
                    for cat_key, cat_info in cats.items():
                        max_gate4 = max(max_gate4, len(cat_info["fallacies"]))
                        print(f"    [Gate 3] {cat_key} ({cat_info['count']})")
                        print(f"      Q: \"{cat_info['gate_question']}\"")
                        for f in cat_info["fallacies"]:
                            print(f"        -> {f}")

        elif "domains" in info:
            # Type 2: D1-D6
            domains = info["domains"]
            max_gate2 = max(max_gate2, len(domains))
            for d_key, d_info in domains.items():
                print(f"  [Gate 2] {d_key}: {d_info['name']} ({d_info['count']}) "
                      f"ERR={d_info['err']}")
                print(f"    Q: \"{d_info['gate_question']}\"")

                fms = d_info["failure_modes"]
                max_gate3 = max(max_gate3, len(fms))
                for fm_key, fm_info in fms.items():
                    max_gate4 = max(max_gate4, len(fm_info["fallacies"]))
                    print(f"    [Gate 3] {fm_key}: {fm_info['name']} ({fm_info['count']})")
                    print(f"      Q: \"{fm_info['gate_question']}\"")
                    for f in fm_info["fallacies"]:
                        print(f"        -> {f}")

        elif "fallacies" in info:
            # Type 3/4/5: Direct to fallacy IDs
            max_gate4 = max(max_gate4, len(info["fallacies"]))
            for f in info["fallacies"]:
                print(f"    -> {f}")

        print()

    print("=" * 78)
    print("GATE BRANCHING SUMMARY")
    print("=" * 78)
    print(f"  Gate 0 (Binary):        2 options")
    print(f"  Gate 1 (Type):          5 options")
    print(f"  Gate 2 (Domain/Sub):    max {max_gate2} options")
    print(f"  Gate 3 (Failure Mode):  max {max_gate3} options")
    print(f"  Gate 4 (Specific ID):   max {max_gate4} options")
    print(f"  Total fallacies: {total}")
    print()

    # Show the gate sequence for each type
    print("=" * 78)
    print("GATE SEQUENCES PER TYPE (number of LLM calls needed)")
    print("=" * 78)
    print("  Type 1 (36): Gate1 -> Gate2(T1A/T1B) -> Gate3(category) -> Gate4(ID)")
    print("    = 4 gates, max branching: 5->2->10->8 = max 10 options at any gate")
    print()
    print("  Type 2 (105): Gate1 -> Gate2(Domain) -> Gate3(FM) -> Gate4(ID)")
    print("    = 4 gates, max branching: 5->6->5->16 = max 16 options at any gate")
    print()
    print("  Type 3 (3): Gate1 -> Gate4(ID)")
    print("    = 2 gates, max branching: 5->3 = max 5 options at any gate")
    print()
    print("  Type 4 (6): Gate1 -> Gate4(ID)")
    print("    = 2 gates, max branching: 5->6 = max 6 options at any gate")
    print()
    print("  Type 5 (6): Gate1 -> Gate4(ID)")
    print("    = 2 gates, max branching: 5->6 = max 6 options at any gate")
    print()
    print("WORST CASE: max 4 LLM calls, max 16 options at Gate 4 (D1.2)")
    print("COMPARISON: Current cascade = 2 calls, max 105 options at Gate 2")
    print()

    # Verify against taxonomy.py
    print("=" * 78)
    print("VERIFICATION: Comparing with taxonomy.py")
    print("=" * 78)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from regulus.fallacies.taxonomy import FALLACIES

    tree_ids = set()
    for vtype, info in CANONICAL_TREE.items():
        if "subtypes" in info:
            for st_info in info["subtypes"].values():
                if "fallacies" in st_info:
                    tree_ids.update(st_info["fallacies"])
                if "categories" in st_info:
                    for cat_info in st_info["categories"].values():
                        tree_ids.update(cat_info["fallacies"])
        elif "domains" in info:
            for d_info in info["domains"].values():
                for fm_info in d_info["failure_modes"].values():
                    tree_ids.update(fm_info["fallacies"])
        elif "fallacies" in info:
            tree_ids.update(info["fallacies"])

    taxonomy_ids = set(FALLACIES.keys())

    in_tree_not_taxonomy = tree_ids - taxonomy_ids
    in_taxonomy_not_tree = taxonomy_ids - tree_ids

    print(f"  Tree IDs:     {len(tree_ids)}")
    print(f"  Taxonomy IDs: {len(taxonomy_ids)}")
    print(f"  Match:        {len(tree_ids & taxonomy_ids)}")

    if in_tree_not_taxonomy:
        print(f"  In tree but NOT in taxonomy.py ({len(in_tree_not_taxonomy)}):")
        for fid in sorted(in_tree_not_taxonomy):
            print(f"    - {fid}")

    if in_taxonomy_not_tree:
        print(f"  In taxonomy.py but NOT in tree ({len(in_taxonomy_not_tree)}):")
        for fid in sorted(in_taxonomy_not_tree):
            print(f"    - {fid}")

    if not in_tree_not_taxonomy and not in_taxonomy_not_tree:
        print("  PERFECT MATCH!")


if __name__ == "__main__":
    print_tree()
