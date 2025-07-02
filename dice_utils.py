import re
import numpy as np

def get_pmf_for_die(sides, reroll_threshold=0, min_roll=0):
    """Generates the PMF for a single die with proper reroll and minimum roll logic."""
    if sides <= 0: return {0: 1.0}

    base_pmf = {i: 1.0 / sides for i in range(1, sides + 1)}

    if reroll_threshold > 0:
        prob_of_reroll = sum(p for o, p in base_pmf.items() if o <= reroll_threshold)
        pmf = {o: p for o, p in base_pmf.items() if o > reroll_threshold}
        if prob_of_reroll > 0:
            for o2, p2 in base_pmf.items():
                pmf[o2] = pmf.get(o2, 0) + prob_of_reroll * p2
    else:
        pmf = base_pmf

    if min_roll > 0:
        new_pmf = {}
        for outcome, prob in pmf.items():
            final_outcome = max(outcome, min_roll)
            new_pmf[final_outcome] = new_pmf.get(final_outcome, 0) + prob
        pmf = new_pmf

    return pmf

def convolve_pmfs(pmf1, pmf2, operation='add'):
    """Convolves two PMFs."""
    new_pmf = {}
    if not pmf1: return pmf2
    if not pmf2: return pmf1
    for o1, p1 in pmf1.items():
        for o2, p2 in pmf2.items():
            new_outcome = o1 + o2 if operation == 'add' else o1 - o2
            new_pmf[new_outcome] = new_pmf.get(new_outcome, 0) + p1 * p2
    return new_pmf

def autoconvolve_pmf(pmf, times, operation='add'):
    """Convolves a PMF with itself a number of times."""
    if times <= 0: return {0: 1.0}
    if times == 1: return pmf
    result = pmf
    for _ in range(times - 1):
        result = convolve_pmfs(result, pmf, operation)
    return result

def apply_advantage_or_disadvantage(pmf, mode='advantage'):
    """Applies (dis)advantage or Elven Accuracy to a PMF."""
    if mode == 'straight' or len(pmf) <= 1: return pmf
    sorted_outcomes = sorted(pmf.items())
    outcomes = [item[0] for item in sorted_outcomes]
    probs = np.array([item[1] for item in sorted_outcomes])
    cdf = np.cumsum(probs)
    if mode == 'advantage': new_cdf = cdf ** 2
    elif mode == 'disadvantage': new_cdf = 1 - (1 - cdf) ** 2
    elif mode == 'elven accuracy': new_cdf = cdf ** 3
    else: return pmf
    new_probs = np.diff(np.insert(new_cdf, 0, 0))
    return {outcomes[i]: new_probs[i] for i in range(len(outcomes))}

# --- Advanced Dice String Parser ---

def parse_and_calculate_pmf(expression):
    """Parses a dice expression and returns its PMF."""
    try:
        if 'adv(' in str(expression) or 'disadv(' in str(expression) or 'ea(' in str(expression):
            if not re.search(r'(adv|disadv|ea)\(\d+d\d+(r\d+)?(m\d+)?\)', str(expression).replace(" ","")):
                 raise ValueError("Advantage/Disadvantage must apply directly to a dice term (e.g., 'adv(1d20)+5' not 'adv(1d20+5)'.")

        tokens = _tokenize(expression)
        if not tokens: return {0: 1.0}
        if tokens[0] in ['+', '-']: tokens.insert(0, '0')

        current_pmf = _calculate_term_pmf(tokens[0])
        i = 1
        while i < len(tokens):
            operator, term = tokens[i], tokens[i+1]
            term_pmf = _calculate_term_pmf(term)
            op_func = 'add' if operator == '+' else 'subtract'
            current_pmf = convolve_pmfs(current_pmf, term_pmf, op_func)
            i += 2
        return current_pmf
    except (ValueError, IndexError, TypeError) as e:
        raise ValueError(f"Invalid dice string: '{expression}'. {e}")

def _tokenize(expression):
    """Splits a dice string into its component parts."""
    expression = str(expression).lower().replace(" ", "")
    if not expression: return []
    token_regex = r'(adv|disadv|ea)\((\d+d\d+(?:r\d+)?(?:m\d+)?)\)|(\d+d\d+(?:r\d+)?(?:m\d+)?)|([+-])|(-?\d+)'
    matches = re.findall(token_regex, expression)
    tokens = []
    for match in matches:
        if match[0]: tokens.append(f"{match[0]}({match[1]})")
        elif match[2]: tokens.append(match[2])
        elif match[3]: tokens.append(match[3])
        elif match[4]: tokens.append(match[4])
    return tokens

def _calculate_term_pmf(term):
    """Calculates the PMF for a single tokenized term."""
    adv_match = re.match(r'(adv|disadv|ea)\((\d+d\d+.*?)\)', term)
    if adv_match:
        mode_str, inner_term = adv_match.groups()
        mode = {'adv': 'advantage', 'disadv': 'disadvantage', 'ea': 'elven accuracy'}[mode_str]
        base_pmf = _calculate_dice_pmf(inner_term)
        return apply_advantage_or_disadvantage(base_pmf, mode)
    if 'd' in term: return _calculate_dice_pmf(term)
    if term.isdigit() or (term.startswith('-') and term[1:].isdigit()): return {int(term): 1.0}
    raise ValueError(f"Unknown term format: '{term}'")

def _calculate_dice_pmf(term):
    """Calculates PMF for a dice term like '2d6r1m2'."""
    sign = -1 if term.startswith('-') else 1
    term = term.lstrip('-')
    d_match = re.match(r'(\d+)d(\d+)', term)
    if not d_match: raise ValueError(f"Invalid dice format: {term}")
    n, s = map(int, d_match.groups())
    reroll_match = re.search(r'r(\d+)', term)
    reroll_threshold = int(reroll_match.group(1)) if reroll_match else 0
    min_roll_match = re.search(r'm(\d+)', term)
    min_roll = int(min_roll_match.group(1)) if min_roll_match else 0
    single_die_pmf = get_pmf_for_die(s, reroll_threshold, min_roll)
    pmf = autoconvolve_pmf(single_die_pmf, n)
    return {k * sign: v for k, v in pmf.items()}

def _get_dice_and_constants(expression):
    """Separates a dice expression into dice terms (with signs) and a single constant."""
    tokens = _tokenize(str(expression))
    if not tokens: return [], 0
    if tokens[0] not in ['+', '-']: tokens.insert(0, '+')

    dice_parts = []
    constant = 0
    i = 0
    while i < len(tokens):
        op, term = tokens[i], tokens[i+1]
        if 'd' in term:
            dice_parts.append((op, term))
        else:
            constant += int(term) if op == '+' else -int(term)
        i += 2
    return dice_parts, constant

def double_dice_in_expression(expression):
    """Takes a dice expression, doubles only the positive dice, and returns the new PMF."""
    dice_parts, constant = _get_dice_and_constants(expression)
    
    all_pmfs = []
    for op, term in dice_parts:
        if op == '+':
            doubled_term = re.sub(r'(\d+)', lambda m: str(int(m.group(1)) * 2), term, 1)
            all_pmfs.append(_calculate_term_pmf(doubled_term))
        else: # op == '-'
            all_pmfs.append(_calculate_term_pmf(f"-{term}"))

    final_dice_pmf = {}
    if all_pmfs:
        final_dice_pmf = all_pmfs[0]
        for next_pmf in all_pmfs[1:]:
            final_dice_pmf = convolve_pmfs(final_dice_pmf, next_pmf)

    return convolve_pmfs(final_dice_pmf, {constant: 1.0})

# --- Mitigation Functions ---
def apply_resistance_vulnerability(pmf, resistance_type):
    """Applies resistance or vulnerability to a PMF."""
    if resistance_type.lower() == "neither": return pmf
    new_pmf = {}
    for outcome, prob in pmf.items():
        new_outcome = int(np.floor(outcome / 2)) if resistance_type.lower() == "resistant" else outcome * 2
        new_pmf[new_outcome] = new_pmf.get(new_outcome, 0) + prob
    return new_pmf
