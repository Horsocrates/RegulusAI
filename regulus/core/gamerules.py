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
    """Single element in a game system (ERRS)."""
    element: str              # What is it
    role: str                 # What function does it serve
    rules: list[str]          # Constraints / behavior rules
    possible_states: list[str] # ALL possible states this element can be in
    current_state: str = ""    # Current state based on question context


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

STEP 2 — BUILD THE ERRS TABLE (Element-Role-Rules-Status):
List every relevant ELEMENT. For each, state Role, Rules, and ALL POSSIBLE STATES.
Then determine CURRENT STATE from the question context.

Format:
ELEMENT: <name>
  ROLE: <function in the game>
  RULE: <specific rule governing this element>
  POSSIBLE STATES: [state1, state2, state3, ...]
  CURRENT STATE: <which state based on question> — REASON: <why>

CRITICAL: The POSSIBLE STATES list must be COMPLETE.
Missing a possible state = missing a rule = wrong answer.

Example for football:
ELEMENT: Ball
  ROLE: Object of play
  RULE: Must cross line of scrimmage for first down
  POSSIBLE STATES: [live, dead, in_flight, out_of_bounds, fumbled, held_by_carrier]
  CURRENT STATE: in_flight — REASON: "pass was thrown"

ELEMENT: Clock
  ROLE: Time tracking
  RULE: Stops on incomplete pass, out of bounds (last 2 min), timeout
  POSSIBLE STATES: [running, stopped]
  CURRENT STATE: running — REASON: no stoppage event yet

Include at minimum:
- The game object (ball/puck/piece) + its current state
- Player/team status (active/fouled/penalized/eliminated)
- Game clock/turn state (running/stopped/overtime)
- Score state if relevant (bonus/match point/game point)
- The specific mechanic in the question + its current state

STEP 3 — STATE TRANSITIONS:
What EVENT does the question describe?
For each element, determine how the event CHANGES its state:

EVENT: <description>
TRANSITIONS:
  <element>: <old_state> → <new_state> (because: <rule>)
  <element>: <old_state> → <new_state> (because: <rule>)
  <element>: <stays same> (because: <rule does not apply>)

STEP 4 — CHAIN TRANSITIONS:
Some transitions trigger OTHER transitions. Follow the chain:

  Transition 1: Ball: in_flight → dead (incomplete pass rule)
  Triggers → Clock: running → stopped (dead ball stops clock rule)
  Triggers → Down: 2nd → 3rd (failed attempt rule)
  No more triggers → chain complete.

STEP 5 — CONCLUSION:
After all transitions resolve, read the FINAL STATE of all elements.
The answer = the final state description.
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
