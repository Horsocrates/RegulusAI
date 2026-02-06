"""
Game Rules analysis module.

Uses ERR (Element-Role-Rule) system tables to answer game rule questions.
Instead of recalling answers from memory, forces structured derivation:
  1. Build system table (elements + roles + rules)
  2. Match event from question to relevant rules
  3. Apply rules to game state → derive answer

Called by D1 when task involves sports rules, board games, card games, etc.
"""

from dataclasses import dataclass, field


@dataclass
class GameElement:
    """Single element in a game system."""
    element: str       # What is it
    role: str          # What function does it serve
    rules: list[str]   # Constraints / behavior rules


@dataclass
class GameAnalysis:
    """Structured game rule analysis."""
    game_identified: str
    elements: list[GameElement]
    event_description: str
    matched_rules: list[str]
    derivation: list[str]      # step-by-step rule application
    conclusion: str


# ── Keywords that indicate game/sport rule questions ────

GAME_KEYWORDS = {
    # Sports
    "football", "soccer", "basketball", "baseball", "tennis",
    "hockey", "cricket", "rugby", "volleyball", "golf",
    "nfl", "nba", "mlb", "nhl", "fifa", "fiba",
    "foul", "penalty", "offside", "touchdown", "goal",
    "innings", "quarter", "half", "overtime", "set", "match",
    "referee", "umpire", "judge",
    "score", "point", "points", "yard", "yards",
    "free throw", "field goal", "home run",
    "red card", "yellow card", "ejection",
    # Board/card games
    "chess", "checkers", "monopoly", "scrabble",
    "poker", "blackjack", "bridge",
    "checkmate", "stalemate", "castling", "en passant",
    "uno", "draw", "discard", "wild card",
    # General game terms
    "rule", "rules", "legal", "illegal", "allowed",
    "turn", "move", "play", "player", "team",
    "win", "lose", "draw", "forfeit",
    "board", "piece", "card", "dice", "token",
    "game", "match", "round", "set",
}


def is_game_question(query: str, d1_content: str = "") -> bool:
    """Check if query is about game/sport rules."""
    combined = (query + " " + d1_content).lower()
    matches = sum(1 for kw in GAME_KEYWORDS if kw in combined)
    return matches >= 2  # at least 2 game-related keywords


# ── Prompts for structured analysis ────────────────────

GAME_SYSTEM_TABLE_PROMPT = """You are analyzing a game/sport rules question.

QUESTION: "{question}"
CONTEXT: "{context}"

STEP 1 — IDENTIFY THE GAME SYSTEM:
What game/sport is this about? Name it explicitly.

STEP 2 — BUILD THE SYSTEM TABLE:
List every relevant ELEMENT of this game that relates to the question.
For each element, state its ROLE and RULES.

Format:
ELEMENT: <name>
  ROLE: <function in the game>
  RULE: <specific rule that governs this element>
  RULE: <additional rule if any>

Include at minimum:
- The game object (ball, puck, piece, card)
- The relevant player positions/roles
- The specific game mechanic mentioned in the question
- The scoring/penalty system relevant to the question

STEP 3 — MATCH EVENT:
What specific EVENT does the question describe?
Which RULES from your table apply to this event?
Format:
EVENT: <description>
MATCHED RULES: <list which rules apply and why>

STEP 4 — APPLY RULES (derive answer):
Starting from the game state described, apply each matched rule in order.
Show each step:
  State: <current state>
  Apply rule: <which rule>
  Result: <new state>

STEP 5 — CONCLUSION:
State the answer derived from rule application.
The answer MUST follow from the rules — do NOT recall from memory.
If rules conflict, state both interpretations.
"""

GAME_RULES_VERIFICATION_PROMPT = """Verify this game rule derivation:

GAME: {game}
QUESTION: {question}
DERIVATION: {derivation}
CONCLUSION: {conclusion}

Check:
1. Are all relevant rules included in the system table?
2. Is the event correctly matched to the right rules?
3. Does each step in the derivation correctly apply the stated rule?
4. Does the conclusion follow from the derivation?
5. Are there any rules that were missed or misapplied?

If everything is correct: [VERIFIED]
If errors found: [ERROR: <specific mistake>] [CORRECTION: <correct application>]
"""
