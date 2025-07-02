import re
import dice_utils as du

def get_full_damage_distribution(d20_string, ac, crit_range, on_hit_pmf_expr, on_miss_damage, brutal_crit_dice_expr):
    """Calculates the final damage distribution for an attack roll."""
    final_pmf = {}

    # --- 1. Parse the Attack Roll --- 
    tokens = du._tokenize(d20_string)
    d20_part = ""
    bonus_parts = []

    # Find the core 1d20 term
    d20_found = False
    d20_idx = -1
    for i, token in enumerate(tokens):
        if '1d20' in token and not d20_found:
            d20_part = token
            d20_found = True
            d20_idx = i
            break # Stop after finding the first 1d20 term

    if not d20_found:
        raise ValueError("Attack roll string must contain a '1d20' term.")

    # Reconstruct the bonus expression from all other tokens
    bonus_tokens = tokens[:d20_idx] + tokens[d20_idx+1:]
    bonus_expr = "".join(bonus_tokens)
    
    d20_pmf = du._calculate_term_pmf(d20_part)
    bonus_pmf = du.parse_and_calculate_pmf(bonus_expr) if bonus_expr else {0: 1.0}

    # --- 2. Calculate Damage PMFs ---
    on_hit_pmf = du.parse_and_calculate_pmf(on_hit_pmf_expr)
    on_miss_pmf = {on_miss_damage: 1.0}
    
    # "Smart" critical damage: double dice from base damage string
    crit_base_pmf = du.double_dice_in_expression(on_hit_pmf_expr)
    
    # Add brutal critical dice if specified
    brutal_crit_pmf = du.parse_and_calculate_pmf(brutal_crit_dice_expr)
    on_crit_pmf = du.convolve_pmfs(crit_base_pmf, brutal_crit_pmf)

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

    return final_pmf

def get_save_damage_distribution(save_dc, save_mod_string, on_fail_pmf_expr, on_succeed_pmf_expr, adv_disadv='straight'):
    """Calculates damage distribution for a saving throw."""
    d20_pmf = du.get_pmf_for_die(20)
    d20_pmf = du.apply_advantage_or_disadvantage(d20_pmf, adv_disadv)
    
    save_bonus_pmf = du.parse_and_calculate_pmf(save_mod_string)
    on_fail_pmf = du.parse_and_calculate_pmf(on_fail_pmf_expr)
    on_succeed_pmf = du.parse_and_calculate_pmf(on_succeed_pmf_expr)

    final_pmf = {}
    
    for d20_roll, d20_prob in d20_pmf.items():
        for bonus, bonus_prob in save_bonus_pmf.items():
            
            total_roll = d20_roll + bonus
            prob_path = d20_prob * bonus_prob
            
            succeeds = total_roll >= save_dc
            
            damage_source_pmf = on_succeed_pmf if succeeds else on_fail_pmf
            
            for damage, damage_prob in damage_source_pmf.items():
                final_pmf[damage] = final_pmf.get(damage, 0) + prob_path * damage_prob
                
    return final_pmf
