import re
import dice_utils as du
import math

def get_full_damage_distribution(d20_string, ac, crit_range, on_hit_pmf_expr, on_miss_damage, on_crit_pmf_expr):
    """Calculates the final damage distribution for an attack roll."""
    final_pmf = {}

    # --- 1. Parse the Attack Roll ---
    tokens = du._tokenize(d20_string)
    d20_part = ""
    bonus_parts = []

    d20_found = False
    d20_idx = -1
    for i, token in enumerate(tokens):
        if '1d20' in token and not d20_found:
            d20_part = token
            d20_found = True
            d20_idx = i
            break

    if not d20_found:
        raise ValueError("Attack roll string must contain a '1d20' term.")

    bonus_tokens = tokens[:d20_idx] + tokens[d20_idx+1:]
    bonus_expr = "".join(bonus_tokens)
    
    d20_pmf = du._calculate_term_pmf(d20_part)
    bonus_pmf = du.parse_and_calculate_pmf(bonus_expr) if bonus_expr else {0: 1.0}

    # --- 2. Calculate Damage PMFs ---
    on_hit_pmf = du.parse_and_calculate_pmf(on_hit_pmf_expr)
    on_miss_pmf = {on_miss_damage: 1.0}
    
    if on_crit_pmf_expr:
        on_crit_pmf = du.parse_and_calculate_pmf(on_crit_pmf_expr)
    else:
        # Default crit: double dice from base damage string
        on_crit_pmf = du.double_dice_in_expression(on_hit_pmf_expr)

    # --- 3. Combine based on Hit/Crit/Miss ---
    for d20_roll, d20_prob in d20_pmf.items():
        if d20_prob == 0: continue

        for bonus, bonus_prob in bonus_pmf.items():
            if bonus_prob == 0: continue

            final_roll_bonus = d20_roll + bonus
            prob_path = d20_prob * bonus_prob

            is_crit = d20_roll >= crit_range[0]
            is_miss = d20_roll == 1
            is_hit = not is_crit and not is_miss and final_roll_bonus >= ac

            damage_source_pmf = on_crit_pmf if is_crit else (on_hit_pmf if is_hit else on_miss_pmf)

            for damage, damage_prob in damage_source_pmf.items():
                final_pmf[damage] = final_pmf.get(damage, 0) + prob_path * damage_prob

    return du.floor_pmf_at_zero(final_pmf)

def get_save_damage_distribution(save_dc, save_roll_string, on_fail_pmf_expr, on_succeed_pmf_expr, save_success_behavior, has_evasion):
    """Calculates damage distribution for a saving throw."""
    # --- 1. Parse the Save Roll ---
    tokens = du._tokenize(save_roll_string)
    d20_part = ""
    bonus_expr = ""
    d20_found = False
    d20_idx = -1

    for i, token in enumerate(tokens):
        if '1d20' in token and not d20_found:
            d20_part = token
            d20_found = True
            d20_idx = i
            break
    
    if not d20_found:
        raise ValueError("Saving throw roll string must contain a '1d20' term.")

    bonus_tokens = tokens[:d20_idx] + tokens[d20_idx+1:]
    bonus_expr = "".join(bonus_tokens)

    d20_pmf = du._calculate_term_pmf(d20_part)
    save_bonus_pmf = du.parse_and_calculate_pmf(bonus_expr) if bonus_expr else {0: 1.0}
    
    # --- 2. Determine the PMF for each outcome (Fail and Succeed) ---
    fail_pmf_base = du.parse_and_calculate_pmf(on_fail_pmf_expr)

    # Determine the damage on a successful save
    if save_success_behavior == "Custom":
        succeed_pmf_base = du.parse_and_calculate_pmf(on_succeed_pmf_expr)
    elif save_success_behavior == "Half Damage":
        succeed_pmf_base = {}
        for k, v in fail_pmf_base.items():
            new_k = math.floor(k/2)
            succeed_pmf_base[new_k] = succeed_pmf_base.get(new_k, 0) + v
    else: # No Damage
        succeed_pmf_base = {0: 1.0}

    # Evasion overrides the normal outcomes
    if has_evasion:
        succeed_pmf = {0: 1.0} # Always 0 damage on success with Evasion
        fail_pmf = {math.floor(k/2): v for k, v in fail_pmf_base.items()} # Half damage on failure
    else:
        succeed_pmf = succeed_pmf_base
        fail_pmf = fail_pmf_base

    # --- 3. Combine based on Save Success/Failure ---
    final_pmf = {}
    for d20_roll, d20_prob in d20_pmf.items():
        for bonus, bonus_prob in save_bonus_pmf.items():
            total_roll = d20_roll + bonus
            prob_path = d20_prob * bonus_prob
            
            # Nat 20 always succeeds, Nat 1 is not an auto-fail for saves
            succeeds = (d20_roll == 20) or (total_roll >= save_dc)
            
            damage_source_pmf = succeed_pmf if succeeds else fail_pmf
            
            for damage, damage_prob in damage_source_pmf.items():
                final_pmf[damage] = final_pmf.get(damage, 0) + prob_path * damage_prob
                
    return du.floor_pmf_at_zero(final_pmf)
