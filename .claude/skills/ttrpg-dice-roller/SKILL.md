---
name: ttrpg-dice-roller
description: Roll TTRPG dice with true random results using cryptographically secure RNG. Supports standard dice notation including keep/drop, rerolls, explosions, success counting, and complex expressions. Use when users need to roll dice for tabletop RPGs (D&D, Pathfinder, Storyteller, Savage Worlds, FATE, etc.) or request random dice results with specific modifiers.
license: MIT License, complete terms in LICENSE.txt
---

# TTRPG Dice Roller

Roll tabletop RPG dice using cryptographically secure random number generation with full dice notation support.

## Usage

Call the dice roller script with a dice notation expression:

```bash
python3 scripts/dice_roller.py "<expression>"
```

The script returns a JSON object with the roll results, full trace of all dice and modifiers, and metadata.

## Supported Notation

### Basic Dice
- `NdM` - Roll N dice with M sides (e.g., `3d6`, `1d20`)
- `dM` - Roll single die (e.g., `d6`, `d20`)
- `d%` or `d00` - Percentile dice (equivalent to `d100`)
- `dF` - FATE/Fudge dice (values: -1, 0, +1)

### Modifiers

**Keep/Drop:**
- `kh3` - Keep highest 3 dice
- `kl2` - Keep lowest 2 dice
- `dh1` - Drop highest 1 die
- `dl1` - Drop lowest 1 die

**Rerolls:**
- `r1` - Reroll 1s indefinitely
- `ro1` - Reroll 1s once only
- `r<=2` - Reroll values ≤2
- `r>=5` - Reroll values ≥5

**Explosions (add extra dice):**
- `!` - Explode on max value
- `!p` - Explode with penetration (-1 penalty on extra dice)
- `!!` - Compound explosion (add to same die)
- `!>=10` - Explode on values ≥10

**Success Counting:**
- `>=7` - Count dice with values ≥7
- `<=3` - Count dice with values ≤3
- `=5` - Count dice with value exactly 5

**Arithmetic:**
- `+`, `-`, `*`, `/` - Standard operators
- `()` - Grouping with parentheses

**Display:**
- `sa` - Sort ascending (display only)
- `sd` - Sort descending (display only)

## Common Examples

### D&D / Pathfinder
```bash
# Ability score generation (4d6, drop lowest)
python3 scripts/dice_roller.py "4d6kh3"

# Attack with advantage
python3 scripts/dice_roller.py "2d20kh1+5"

# Attack with disadvantage
python3 scripts/dice_roller.py "2d20kl1+3"

# Critical hit damage
python3 scripts/dice_roller.py "4d8+2d6+4"
```

### Storyteller / World of Darkness
```bash
# Dice pool with threshold (count successes ≥8)
python3 scripts/dice_roller.py "10d10>=8"

# Dice pool with explosions on 10s (not yet supported: requires two comparators)
# Workaround: Roll explosions separately
python3 scripts/dice_roller.py "10d10!"
```

### Savage Worlds
```bash
# Exploding d6 with penetration
python3 scripts/dice_roller.py "1d6!p"

# Skill check with wild die
python3 scripts/dice_roller.py "1d8!+1d6!"
```

### FATE / Fudge
```bash
# Standard FATE roll
python3 scripts/dice_roller.py "4dF"

# FATE with skill modifier
python3 scripts/dice_roller.py "4dF+3"
```

### Complex Expressions
```bash
# Multiple dice pools with modifiers
python3 scripts/dice_roller.py "(4d6kh3)+(2d8)+3"

# Reroll 1s once, then keep highest 3
python3 scripts/dice_roller.py "4d6ro1kh3"

# Exploding dice with arithmetic
python3 scripts/dice_roller.py "3d6!+2d4+10"
```

## Output Format

### Success Response
```json
{
  "ok": true,
  "final": 15,
  "type": "sum",
  "trace": [
    {
      "term": "4d6kh3",
      "rolls": [
        {"value": 6},
        {"value": 5},
        {"value": 4},
        {"value": 2}
      ],
      "keptValues": [6, 5, 4],
      "sum": 15
    }
  ],
  "rng": {
    "source": "CSPRNG",
    "method": "rejectionSampling"
  },
  "limits": {
    "maxDice": 1000,
    "maxExplosions": 100
  },
  "version": "dice-1.0.0"
}
```

### Success Counting Response
```json
{
  "ok": true,
  "final": 7,
  "type": "success_count",
  "trace": [
    {
      "term": "10d10>=7",
      "rolls": [
        {"value": 9, "success": true},
        {"value": 6, "success": false}
      ],
      "threshold": ">=7",
      "successes": 7
    }
  ]
}
```

### Error Response
```json
{
  "ok": false,
  "error": {
    "type": "ParseError",
    "message": "Expected number after 'kh'",
    "position": 4,
    "input": "4d6kh"
  }
}
```

## Error Types

- **ParseError** - Invalid syntax or unexpected token
- **SemanticError** - Invalid dice rules (e.g., keep more dice than rolled)
- **LimitError** - Exceeded safety limits
- **RuntimeError** - Unexpected execution error (division by zero, etc.)

## Implementation Details

- Uses Python's `secrets` module for CSPRNG
- Rejection sampling eliminates modulo bias
- Safety limits: max 1000 dice per term, max 100 explosions, max 10000 rerolls
- Full trace includes all intermediate values for transparency

## Workflow

1. Parse user's dice notation string into expressions
2. Call the dice roller script with the expression
3. Parse the JSON output
4. Present results to the user in a clear, readable format
5. Include relevant trace information if the user wants to see individual dice results

When presenting results to users:
- Always show the final result prominently
- Show the expression that was rolled
- Optionally show individual dice values from the trace (if user wants details)
- For complex expressions with multiple terms, show the breakdown
- Format large numbers with appropriate notation (commas, etc.)
