#!/usr/bin/env python3
"""
TTRPG Dice Notation Parser and Roller
True random dice rolling with cryptographically secure RNG
"""

import json
import re
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

VERSION = "dice-1.0.0"

# Safety limits
MAX_DICE = 1000
MAX_SIDES = 1_000_000_000
MAX_EXPLOSIONS = 100
MAX_REROLLS = 10000
MAX_RECURSION = 32
MAX_EVAL_TIME_MS = 100


class ResultType(Enum):
    SUM = "sum"
    SUCCESS_COUNT = "success_count"


@dataclass
class DieRoll:
    """Represents a single die roll with its history"""
    value: int
    rerolls: List[int] = None
    explodes: List[Dict[str, int]] = None
    success: Optional[bool] = None

    def __post_init__(self):
        if self.rerolls is None:
            self.rerolls = []
        if self.explodes is None:
            self.explodes = []

    def to_dict(self):
        d = {"value": self.value}
        if self.rerolls:
            d["rerolls"] = self.rerolls
        if self.explodes:
            d["explodes"] = self.explodes
        if self.success is not None:
            d["success"] = self.success
        return d


@dataclass
class DiceTrace:
    """Trace of a single dice term evaluation"""
    term: str
    rolls: List[DieRoll]
    keptValues: Optional[List[int]] = None
    sum: Optional[int] = None
    threshold: Optional[str] = None
    successes: Optional[int] = None

    def to_dict(self):
        d = {
            "term": self.term,
            "rolls": [r.to_dict() for r in self.rolls]
        }
        if self.keptValues is not None:
            d["keptValues"] = self.keptValues
        if self.sum is not None:
            d["sum"] = self.sum
        if self.threshold is not None:
            d["threshold"] = self.threshold
        if self.successes is not None:
            d["successes"] = self.successes
        return d


class DiceError(Exception):
    """Base exception for dice operations"""
    pass


class ParseError(DiceError):
    """Error during parsing"""
    def __init__(self, message: str, position: int, input_str: str):
        self.message = message
        self.position = position
        self.input_str = input_str
        super().__init__(message)


class SemanticError(DiceError):
    """Error in dice semantics"""
    pass


class LimitError(DiceError):
    """Safety limit exceeded"""
    pass


class CSPRNG:
    """Cryptographically secure random number generator with rejection sampling"""

    @staticmethod
    def roll_die(sides: int) -> int:
        """
        Roll a die with the given number of sides using CSPRNG.
        Uses rejection sampling to eliminate modulo bias.

        Args:
            sides: Number of sides on the die

        Returns:
            Random integer from 1 to sides (inclusive)
        """
        if sides < 1:
            raise ValueError("Die must have at least 1 side")
        if sides > MAX_SIDES:
            raise LimitError(f"Die cannot have more than {MAX_SIDES} sides")

        # Special case: d1 always returns 1
        if sides == 1:
            return 1

        # Calculate the bound for rejection sampling
        # We use 256 as the modulus for a single byte
        bytes_needed = (sides.bit_length() + 7) // 8
        max_value = (1 << (bytes_needed * 8))
        bound = (max_value // sides) * sides

        # Rejection sampling loop
        attempts = 0
        while attempts < 10000:  # Prevent infinite loops
            random_bytes = secrets.token_bytes(bytes_needed)
            value = int.from_bytes(random_bytes, byteorder='big')
            if value < bound:
                return (value % sides) + 1
            attempts += 1

        # Fallback (should be extremely rare)
        return secrets.randbelow(sides) + 1


class Tokenizer:
    """Tokenize dice notation strings"""

    TOKEN_PATTERN = re.compile(
        r'(\d+)|'              # Numbers
        r'(d[%F]|d\d+|d00)|'  # Dice
        r'(kh|kl|dh|dl)|'     # Keep/drop
        r'(ro?|!{1,2}p?)|'    # Reroll/explode
        r'(>=|<=|=|>|<)|'     # Comparators
        r'(sa|sd)|'            # Sort
        r'([+\-*/()])|'        # Operators and parens
        r'(#[^\n]*)|'          # Comments
        r'(\s+)',              # Whitespace
        re.IGNORECASE
    )

    def __init__(self, text: str):
        self.text = text.strip()
        self.tokens = []
        self.position = 0
        self._tokenize()

    def _tokenize(self):
        """Parse the input into tokens"""
        for match in self.TOKEN_PATTERN.finditer(self.text):
            token_text = match.group(0)
            # Skip whitespace and comments
            if match.group(9) or match.group(8):
                continue

            self.tokens.append({
                'text': token_text,
                'pos': match.start()
            })

    def peek(self, offset: int = 0) -> Optional[str]:
        """Look at token without consuming it"""
        idx = self.position + offset
        if idx < len(self.tokens):
            return self.tokens[idx]['text']
        return None

    def consume(self, expected: Optional[str] = None) -> str:
        """Consume and return next token"""
        if self.position >= len(self.tokens):
            if expected:
                raise ParseError(
                    f"Expected '{expected}' but reached end of input",
                    len(self.text),
                    self.text
                )
            raise ParseError("Unexpected end of input", len(self.text), self.text)

        token = self.tokens[self.position]
        self.position += 1

        if expected and token['text'].lower() != expected.lower():
            raise ParseError(
                f"Expected '{expected}' but got '{token['text']}'",
                token['pos'],
                self.text
            )

        return token['text']

    def at_end(self) -> bool:
        """Check if at end of tokens"""
        return self.position >= len(self.tokens)


class DiceParser:
    """Parse dice notation into an AST"""

    def __init__(self, text: str):
        self.tokenizer = Tokenizer(text)
        self.recursion_depth = 0

    def parse(self) -> Any:
        """Parse the complete expression"""
        if self.tokenizer.at_end():
            raise ParseError("Empty expression", 0, self.tokenizer.text)

        result = self.parse_expression()

        if not self.tokenizer.at_end():
            token = self.tokenizer.peek()
            raise ParseError(
                f"Unexpected token '{token}' after expression",
                self.tokenizer.tokens[self.tokenizer.position]['pos'],
                self.tokenizer.text
            )

        return result

    def parse_expression(self) -> Any:
        """Parse addition and subtraction"""
        left = self.parse_term()

        while not self.tokenizer.at_end():
            op = self.tokenizer.peek()
            if op not in ['+', '-']:
                break

            self.tokenizer.consume()
            right = self.parse_term()
            left = ('binary_op', op, left, right)

        return left

    def parse_term(self) -> Any:
        """Parse multiplication and division"""
        left = self.parse_factor()

        while not self.tokenizer.at_end():
            op = self.tokenizer.peek()
            if op not in ['*', '/']:
                break

            self.tokenizer.consume()
            right = self.parse_factor()
            left = ('binary_op', op, left, right)

        return left

    def parse_factor(self) -> Any:
        """Parse unary minus and parentheses"""
        token = self.tokenizer.peek()

        if token == '-':
            self.tokenizer.consume()
            operand = self.parse_factor()
            return ('unary_op', '-', operand)

        if token == '(':
            self.recursion_depth += 1
            if self.recursion_depth > MAX_RECURSION:
                raise LimitError(f"Exceeded maximum recursion depth of {MAX_RECURSION}")

            self.tokenizer.consume('(')
            expr = self.parse_expression()
            self.tokenizer.consume(')')
            self.recursion_depth -= 1
            return expr

        return self.parse_primary()

    def parse_primary(self) -> Any:
        """Parse numbers and dice terms"""
        token = self.tokenizer.peek()

        if not token:
            raise ParseError("Unexpected end of expression", len(self.tokenizer.text), self.tokenizer.text)

        # Check for dice notation
        if token.lower().startswith('d') or (token.isdigit() and
                                              self.tokenizer.peek(1) and
                                              self.tokenizer.peek(1).lower().startswith('d')):
            return self.parse_dice()

        # Parse number
        if token.isdigit() or (token.startswith('-') and token[1:].isdigit()):
            num = int(self.tokenizer.consume())
            return ('number', num)

        raise ParseError(f"Unexpected token '{token}'",
                        self.tokenizer.tokens[self.tokenizer.position]['pos'],
                        self.tokenizer.text)

    def parse_dice(self) -> Tuple:
        """Parse a dice term (e.g., 4d6kh3+2)"""
        # Parse number of dice
        count_token = self.tokenizer.peek()
        if count_token and count_token.isdigit():
            count = int(self.tokenizer.consume())
        else:
            count = 1

        # Parse 'd' and sides
        die_token = self.tokenizer.consume()
        if not die_token.lower().startswith('d'):
            raise ParseError(f"Expected dice notation, got '{die_token}'",
                           self.tokenizer.tokens[self.tokenizer.position - 1]['pos'],
                           self.tokenizer.text)

        sides_str = die_token[1:].lower()
        if sides_str == '%' or sides_str == '00':
            sides = 100
            die_type = 'd%'
        elif sides_str == 'f' or sides_str == 'f.2':
            sides = 3  # FATE dice: -1, 0, +1
            die_type = 'dF'
        else:
            try:
                sides = int(sides_str)
                die_type = 'd'
            except ValueError:
                raise ParseError(f"Invalid dice sides '{sides_str}'",
                               self.tokenizer.tokens[self.tokenizer.position - 1]['pos'],
                               self.tokenizer.text)

        if count > MAX_DICE:
            raise LimitError(f"Cannot roll more than {MAX_DICE} dice per term")
        if sides > MAX_SIDES:
            raise LimitError(f"Die cannot have more than {MAX_SIDES} sides")
        if count < 1:
            raise SemanticError("Must roll at least 1 die")
        if sides < 1:
            raise SemanticError("Die must have at least 1 side")

        # Parse modifiers
        modifiers = self.parse_dice_modifiers()

        return ('dice', count, sides, die_type, modifiers)

    def parse_dice_modifiers(self) -> Dict:
        """Parse dice modifiers (reroll, explode, keep/drop, comparator)"""
        mods = {
            'reroll': None,
            'explode': None,
            'keep': None,
            'sort': None,
            'comparator': None
        }

        while not self.tokenizer.at_end():
            token = self.tokenizer.peek()
            if not token:
                break

            token_lower = token.lower()

            # Reroll
            if token_lower in ['r', 'ro']:
                self.tokenizer.consume()
                once = token_lower == 'ro'
                condition = self.parse_condition()
                mods['reroll'] = {'once': once, 'condition': condition}

            # Explode
            elif token_lower in ['!', '!!', '!p']:
                explode_token = self.tokenizer.consume()
                penetrating = 'p' in explode_token.lower()
                compound = len(explode_token) == 2 and explode_token == '!!'
                condition = self.parse_condition(default_op='>=', default_value='max')
                mods['explode'] = {
                    'penetrating': penetrating,
                    'compound': compound,
                    'condition': condition
                }

            # Keep/Drop
            elif token_lower in ['kh', 'kl', 'dh', 'dl']:
                mod_type = self.tokenizer.consume().lower()
                if self.tokenizer.at_end() or not self.tokenizer.peek().isdigit():
                    raise ParseError(f"Expected number after '{mod_type}'",
                                   self.tokenizer.tokens[self.tokenizer.position]['pos'] if not self.tokenizer.at_end() else len(self.tokenizer.text),
                                   self.tokenizer.text)
                number = int(self.tokenizer.consume())
                mods['keep'] = {'type': mod_type, 'count': number}

            # Sort
            elif token_lower in ['sa', 'sd']:
                sort_type = self.tokenizer.consume().lower()
                mods['sort'] = sort_type

            # Comparator
            elif token_lower in ['>=', '<=', '=', '>', '<']:
                op = self.tokenizer.consume()
                if self.tokenizer.at_end() or not self.tokenizer.peek().isdigit():
                    raise ParseError(f"Expected number after comparator '{op}'",
                                   self.tokenizer.tokens[self.tokenizer.position]['pos'] if not self.tokenizer.at_end() else len(self.tokenizer.text),
                                   self.tokenizer.text)
                value = int(self.tokenizer.consume())
                mods['comparator'] = {'op': op, 'value': value}
                break  # Comparator ends dice modifiers

            else:
                break  # Not a modifier

        return mods

    def parse_condition(self, default_op: str = '=', default_value: Union[int, str] = 1) -> Dict:
        """Parse a condition for reroll/explode (e.g., >=10, 1, etc.)"""
        token = self.tokenizer.peek()

        if token and token in ['>=', '<=', '=', '>', '<']:
            op = self.tokenizer.consume()
            if self.tokenizer.at_end() or not self.tokenizer.peek().isdigit():
                raise ParseError(f"Expected number after operator '{op}'",
                               self.tokenizer.tokens[self.tokenizer.position]['pos'] if not self.tokenizer.at_end() else len(self.tokenizer.text),
                               self.tokenizer.text)
            value = int(self.tokenizer.consume())
            return {'op': op, 'value': value}
        elif token and token.isdigit():
            value = int(self.tokenizer.consume())
            return {'op': '=', 'value': value}
        else:
            # Default condition
            return {'op': default_op, 'value': default_value}


class DiceEvaluator:
    """Evaluate parsed dice expressions"""

    def __init__(self):
        self.traces = []
        self.rng = CSPRNG()

    def evaluate(self, ast: Any) -> Tuple[Union[int, float], List[DiceTrace]]:
        """Evaluate the AST and return result with traces"""
        self.traces = []
        result = self._eval_node(ast)
        return result, self.traces

    def _eval_node(self, node: Any) -> Union[int, float]:
        """Recursively evaluate an AST node"""
        if not isinstance(node, tuple):
            raise ValueError(f"Invalid AST node: {node}")

        node_type = node[0]

        if node_type == 'number':
            return node[1]

        elif node_type == 'binary_op':
            _, op, left, right = node
            left_val = self._eval_node(left)
            right_val = self._eval_node(right)

            if op == '+':
                return left_val + right_val
            elif op == '-':
                return left_val - right_val
            elif op == '*':
                return left_val * right_val
            elif op == '/':
                if right_val == 0:
                    raise DiceError("Division by zero")
                return left_val / right_val

        elif node_type == 'unary_op':
            _, op, operand = node
            operand_val = self._eval_node(operand)
            if op == '-':
                return -operand_val

        elif node_type == 'dice':
            return self._eval_dice(node)

        raise ValueError(f"Unknown node type: {node_type}")

    def _eval_dice(self, node: Tuple) -> int:
        """Evaluate a dice term"""
        _, count, sides, die_type, modifiers = node

        # Roll the dice
        rolls = []
        for _ in range(count):
            if die_type == 'dF':
                # FATE dice: -1, 0, +1
                value = self.rng.roll_die(3) - 2
            else:
                value = self.rng.roll_die(sides)

            rolls.append(DieRoll(value=value))

        # Apply rerolls
        if modifiers['reroll']:
            self._apply_rerolls(rolls, sides, die_type, modifiers['reroll'])

        # Apply explosions
        if modifiers['explode']:
            self._apply_explosions(rolls, sides, die_type, modifiers['explode'])

        # Apply keep/drop
        kept_values = None
        if modifiers['keep']:
            kept_values = self._apply_keep_drop(rolls, modifiers['keep'])

        # Apply sort (display only, doesn't affect calculation)
        if modifiers['sort']:
            if modifiers['sort'] == 'sa':
                rolls.sort(key=lambda r: r.value)
            else:  # sd
                rolls.sort(key=lambda r: r.value, reverse=True)

        # Build term string for trace
        term_str = f"{count}d{sides if die_type == 'd' else die_type.split('d')[1]}"
        for k, v in modifiers.items():
            if v is not None and k not in ['sort', 'comparator']:
                if k == 'reroll':
                    term_str += f"r{'o' if v['once'] else ''}{self._format_condition(v['condition'])}"
                elif k == 'explode':
                    term_str += f"!{'!' if v['compound'] else ''}{'p' if v['penetrating'] else ''}{self._format_condition(v['condition']) if v['condition']['value'] != 'max' else ''}"
                elif k == 'keep':
                    term_str += f"{v['type']}{v['count']}"

        # Apply comparator (success counting)
        if modifiers['comparator']:
            comp = modifiers['comparator']
            term_str += f"{comp['op']}{comp['value']}"
            successes = self._count_successes(rolls, comp, kept_values)

            trace = DiceTrace(
                term=term_str,
                rolls=rolls,
                threshold=f"{comp['op']}{comp['value']}",
                successes=successes
            )
            self.traces.append(trace)
            return successes

        # Sum the results
        if kept_values is not None:
            result = sum(kept_values)
            trace = DiceTrace(
                term=term_str,
                rolls=rolls,
                keptValues=kept_values,
                sum=result
            )
        else:
            values = [r.value for r in rolls]
            if die_type == 'dF':
                # For FATE dice, include explosion values
                for r in rolls:
                    if r.explodes:
                        values.extend([e['value'] for e in r.explodes])
            result = sum(values)
            trace = DiceTrace(
                term=term_str,
                rolls=rolls,
                sum=result
            )

        self.traces.append(trace)
        return result

    def _apply_rerolls(self, rolls: List[DieRoll], sides: int, die_type: str, reroll_spec: Dict):
        """Apply reroll rules to dice"""
        condition = reroll_spec['condition']
        once = reroll_spec['once']

        for roll in rolls:
            reroll_count = 0
            while self._check_condition(roll.value, condition) and reroll_count < MAX_REROLLS:
                old_value = roll.value
                if die_type == 'dF':
                    roll.value = self.rng.roll_die(3) - 2
                else:
                    roll.value = self.rng.roll_die(sides)
                roll.rerolls.append(old_value)
                reroll_count += 1

                if once:
                    break

            if reroll_count >= MAX_REROLLS:
                raise LimitError(f"Exceeded maximum rerolls of {MAX_REROLLS}")

    def _apply_explosions(self, rolls: List[DieRoll], sides: int, die_type: str, explode_spec: Dict):
        """Apply explosion rules to dice"""
        condition = explode_spec['condition']
        penetrating = explode_spec['penetrating']

        # Resolve 'max' value
        if condition['value'] == 'max':
            if die_type == 'dF':
                condition['value'] = 1
            else:
                condition['value'] = sides

        for roll in rolls:
            explosion_count = 0
            current_value = roll.value

            while self._check_condition(current_value, condition) and explosion_count < MAX_EXPLOSIONS:
                if die_type == 'dF':
                    new_value = self.rng.roll_die(3) - 2
                else:
                    new_value = self.rng.roll_die(sides)

                if penetrating and new_value > 0:
                    new_value -= 1

                roll.explodes.append({'value': new_value})
                current_value = new_value
                explosion_count += 1

            if explosion_count >= MAX_EXPLOSIONS:
                raise LimitError(f"Exceeded maximum explosions of {MAX_EXPLOSIONS}")

    def _apply_keep_drop(self, rolls: List[DieRoll], keep_spec: Dict) -> List[int]:
        """Apply keep/drop rules and return kept values"""
        keep_type = keep_spec['type']
        count = keep_spec['count']

        # Get all values (including explosions)
        all_values = []
        for roll in rolls:
            total = roll.value
            if roll.explodes:
                total += sum(e['value'] for e in roll.explodes)
            all_values.append(total)

        if count > len(all_values):
            raise SemanticError(f"Cannot keep/drop {count} from {len(all_values)} dice")

        sorted_values = sorted(all_values, reverse=True)

        if keep_type == 'kh':  # Keep highest
            return sorted_values[:count]
        elif keep_type == 'kl':  # Keep lowest
            return sorted_values[-count:]
        elif keep_type == 'dh':  # Drop highest
            return sorted_values[count:]
        elif keep_type == 'dl':  # Drop lowest
            return sorted_values[:-count]

    def _count_successes(self, rolls: List[DieRoll], comparator: Dict, kept_values: Optional[List[int]]) -> int:
        """Count successes based on comparator"""
        values = kept_values if kept_values is not None else [r.value for r in rolls]

        # Mark successes on rolls
        for i, roll in enumerate(rolls):
            if kept_values is None or i < len(values):
                roll.success = self._check_condition(roll.value, comparator)

        return sum(1 for v in values if self._check_condition(v, comparator))

    def _check_condition(self, value: int, condition: Dict) -> bool:
        """Check if a value meets a condition"""
        op = condition['op']
        threshold = condition['value']

        if op == '=':
            return value == threshold
        elif op == '>':
            return value > threshold
        elif op == '>=':
            return value >= threshold
        elif op == '<':
            return value < threshold
        elif op == '<=':
            return value <= threshold

        return False

    def _format_condition(self, condition: Dict) -> str:
        """Format a condition as a string"""
        if condition['op'] == '=' and condition['value'] != 'max':
            return str(condition['value'])
        return f"{condition['op']}{condition['value']}"


def roll_dice(expression: str) -> Dict[str, Any]:
    """
    Main entry point: parse and evaluate a dice expression.

    Args:
        expression: Dice notation string (e.g., "4d6kh3+2")

    Returns:
        Dict with structure:
        {
            "ok": True/False,
            "final": numeric result,
            "type": "sum" or "success_count",
            "trace": list of dice term traces,
            "rng": RNG metadata,
            "limits": safety limits used,
            "version": version string
        }

        Or on error:
        {
            "ok": False,
            "error": {
                "type": error type,
                "message": error message,
                ...
            }
        }
    """
    try:
        # Parse the expression
        parser = DiceParser(expression)
        ast = parser.parse()

        # Evaluate the expression
        evaluator = DiceEvaluator()
        result, traces = evaluator.evaluate(ast)

        # Determine result type
        result_type = ResultType.SUCCESS_COUNT if any(
            t.successes is not None for t in traces
        ) else ResultType.SUM

        # Build response
        return {
            "ok": True,
            "final": int(result) if isinstance(result, (int, float)) and result == int(result) else result,
            "type": result_type.value,
            "trace": [t.to_dict() for t in traces],
            "rng": {
                "source": "CSPRNG",
                "method": "rejectionSampling"
            },
            "limits": {
                "maxDice": MAX_DICE,
                "maxExplosions": MAX_EXPLOSIONS
            },
            "version": VERSION
        }

    except ParseError as e:
        return {
            "ok": False,
            "error": {
                "type": "ParseError",
                "message": e.message,
                "position": e.position,
                "input": e.input_str
            }
        }

    except (SemanticError, LimitError, DiceError) as e:
        return {
            "ok": False,
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "input": expression
            }
        }

    except Exception as e:
        return {
            "ok": False,
            "error": {
                "type": "RuntimeError",
                "message": f"Unexpected error: {str(e)}",
                "input": expression
            }
        }


def main():
    """CLI interface for testing"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: dice_roller.py <expression>")
        print("Examples:")
        print("  dice_roller.py '4d6kh3+2'")
        print("  dice_roller.py '10d10>=7!'")
        print("  dice_roller.py '2d20kh1+8'")
        sys.exit(1)

    expression = ' '.join(sys.argv[1:])
    result = roll_dice(expression)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
