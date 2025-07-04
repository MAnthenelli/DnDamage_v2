import streamlit as st
import pandas as pd
import altair as alt
import dice_utils as du
import dnd_utils as dndu
import numpy as np
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(layout="wide")

# --- Session State and Initialization ---
def init_session_state(key, value):
    if key not in st.session_state:
        st.session_state[key] = value

init_session_state('comparison_data', [])
init_session_state('current_pmf', {})
init_session_state('multi_actions', [])
init_session_state('multi_action_pmf', {})
init_session_state('action_groups', [])
init_session_state('current_calculation', {})
init_session_state('editing_action_index', None)

# --- Helper Functions ---
def pmf_to_df(pmf, name="current"):
    if not pmf: return pd.DataFrame()
    df = pd.DataFrame(list(pmf.items()), columns=["Value", "Probability"])
    df["Comparison"] = name
    df = df.sort_values("Value").reset_index(drop=True)
    df["CDF"] = 1 - df["Probability"].cumsum() + df["Probability"]
    return df

# --- Multi-Action Functions ---
def calculate_multi_action_pmf():
    if not st.session_state.multi_actions:
        st.session_state.multi_action_pmf = {}
        return
    
    combined_pmf = {0: 1.0}
    for action in st.session_state.multi_actions:
        combined_pmf = du.convolve_pmfs(combined_pmf, action['pmf'])
        
    st.session_state.multi_action_pmf = combined_pmf

def get_action_params(action_type):
    params = {'action_type': action_type}
    try:
        if action_type == "Dice Roll":
            params['dice_roll_string'] = st.session_state.dice_roll_string
        elif action_type == "Attack Roll":
            params.update({
                'attack_roll_string': st.session_state.attack_roll_string,
                'enemy_ac': st.session_state.enemy_ac,
                'enemy_resistance': st.session_state.enemy_resistance,
                'dmg_string': st.session_state.dmg_string,
                'crit_range': st.session_state.crit_range,
                'use_custom_crit': st.session_state.use_custom_crit,
                'custom_crit_string': st.session_state.get('custom_crit_string', ''),
                'dmg_on_miss': st.session_state.dmg_on_miss,
                'num_actions': st.session_state.num_actions
            })
        elif action_type == "Saving Throw":
            params.update({
                'save_roll_string': st.session_state.save_roll_string,
                'save_dc': st.session_state.save_dc,
                'save_resistance': st.session_state.save_resistance,
                'has_evasion': st.session_state.has_evasion,
                'fail_dmg_string': st.session_state.fail_dmg_string,
                'save_success_behavior': st.session_state.save_success_behavior,
                'succ_dmg_string': st.session_state.get('succ_dmg_string', ''),
                'num_actions': st.session_state.num_actions
            })
    except KeyError as e:
        st.error(f"Error getting parameters: Missing key {e}. This can happen if you switch action types after calculating.")
        return None
    return params

def set_action_params(params):
    st.session_state.action_type = params['action_type']
    for key, value in params.items():
        if key != 'action_type':
            st.session_state[key] = value

# --- UI Rendering ---
st.title("D&D Dice & Damage Calculator")

with st.sidebar:
    st.header("Multi-Action Builder")
    st.write("Build a sequence of actions to see the combined damage distribution.")

    st.text_input("Name for Current Calculation", "My Action", key="action_name")
    if st.button("Add Current Calculation to Sequence"):
        if st.session_state.current_calculation:
            action_name = st.session_state.action_name
            # Use the stored calculation instead of grabbing current (potentially mismatched) params
            st.session_state.multi_actions.append({
                'name': action_name, 
                'pmf': st.session_state.current_calculation['pmf'], 
                'params': st.session_state.current_calculation['params']
            })
            calculate_multi_action_pmf()

    st.write("**Action Sequence:**")
    for i, action in enumerate(st.session_state.multi_actions):
        cols = st.columns([0.6, 0.2, 0.2])
        new_name = cols[0].text_input("", value=action['name'], key=f"action_name_{i}")
        if new_name != action['name']:
            st.session_state.multi_actions[i]['name'] = new_name
        if cols[1].button("Edit", key=f"edit_action_{i}"):
            st.session_state.editing_action_index = i
            set_action_params(action['params'])
            st.rerun()
        if cols[2].button("X", key=f"remove_action_{i}"):
            st.session_state.multi_actions.pop(i)
            calculate_multi_action_pmf()
            st.rerun()

    if st.session_state.multi_actions:
        if st.button("Clear All Actions"):
            st.session_state.multi_actions = []
            st.session_state.multi_action_pmf = {}

main_cols = st.columns([0.45, 0.55])

with main_cols[0]:
    st.header("Controls")
    action_type = st.radio("Select Action Type:", ["Dice Roll", "Attack Roll", "Saving Throw"], horizontal=True, key="action_type")

    # --- DICE ROLL FORM ---
    if action_type == "Dice Roll":
        with st.form(key='dice_roll_form'):
            st.text_input("Dice String", "1d4m2", key="dice_roll_string")
            
            if st.session_state.editing_action_index is not None:
                if st.form_submit_button("Update Action"):
                    params = get_action_params(action_type)
                    if params:
                        pmf = du.parse_and_calculate_pmf(params['dice_roll_string'])
                        st.session_state.multi_actions[st.session_state.editing_action_index]['pmf'] = pmf
                        st.session_state.multi_actions[st.session_state.editing_action_index]['params'] = params
                        calculate_multi_action_pmf()
                        st.session_state.editing_action_index = None
                        st.rerun()
                if st.form_submit_button("Cancel"):
                    st.session_state.editing_action_index = None
                    st.rerun()
            else:
                if st.form_submit_button("Calculate"):
                    pmf = du.parse_and_calculate_pmf(st.session_state.dice_roll_string)
                    params = get_action_params(action_type)
                    st.session_state.current_calculation = {'pmf': pmf, 'params': params}
                    st.session_state.current_pmf = pmf

    # --- ATTACK ROLL FORM ---
    if action_type == "Attack Roll":
        with st.form(key='attack_roll_form'):
            st.text_input("Attack Roll String", "adv(1d20) + 5", key="attack_roll_string")
            with st.expander("**Target**", expanded=True):
                st.number_input("Armor Class", 1, 30, 15, key="enemy_ac")
                st.radio("Resistance/Vulnerability", ["Neither", "Resistant", "Vulnerable"], horizontal=True, key="enemy_resistance")
            with st.expander("**Damage**", expanded=True):
                st.text_input("Damage (on hit)", "1d8+3", key="dmg_string")
                st.number_input("Crit on d20 roll of...", 1, 20, 20, key="crit_range")
                
                if 'default_crit_string' not in st.session_state or st.session_state.dmg_string != st.session_state.get('_last_dmg_string_for_crit'):
                    st.session_state.default_crit_string = du.get_doubled_dice_string(st.session_state.dmg_string)
                    st.session_state._last_dmg_string_for_crit = st.session_state.dmg_string

                use_custom_crit = st.checkbox("Custom damage on crit", key="use_custom_crit")
                if use_custom_crit:
                    st.text_input("Damage on Crit", value=st.session_state.default_crit_string, key="custom_crit_string")
                
                st.number_input("Flat Damage on Miss", 0, key="dmg_on_miss")
            with st.expander("**Scenario**"):
                st.number_input("Number of Identical Actions", 1, 10, 1, key="num_actions")
            
            if st.session_state.editing_action_index is not None:
                if st.form_submit_button("Update Action"):
                    params = get_action_params(action_type)
                    if params:
                        custom_crit_expr = params['custom_crit_string'] if params['use_custom_crit'] else ""
                        single_action_pmf = dndu.get_full_damage_distribution(
                            d20_string=params['attack_roll_string'], ac=params['enemy_ac'],
                            crit_range=[params['crit_range'], 20], on_hit_pmf_expr=params['dmg_string'],
                            on_miss_damage=params['dmg_on_miss'], on_crit_pmf_expr=custom_crit_expr)
                        total_pmf = du.autoconvolve_pmf(single_action_pmf, params['num_actions'])
                        final_pmf = du.apply_resistance_vulnerability(total_pmf, params['enemy_resistance'])
                        
                        st.session_state.multi_actions[st.session_state.editing_action_index]['pmf'] = final_pmf
                        st.session_state.multi_actions[st.session_state.editing_action_index]['params'] = params
                        calculate_multi_action_pmf()
                        st.session_state.editing_action_index = None
                        st.rerun()
                if st.form_submit_button("Cancel"):
                    st.session_state.editing_action_index = None
                    st.rerun()
            else:
                if st.form_submit_button("Calculate"):
                    params = get_action_params(action_type)
                    if params:
                        custom_crit_expr = params['custom_crit_string'] if params['use_custom_crit'] else ""
                        single_action_pmf = dndu.get_full_damage_distribution(
                            d20_string=params['attack_roll_string'], ac=params['enemy_ac'],
                            crit_range=[params['crit_range'], 20], on_hit_pmf_expr=params['dmg_string'],
                            on_miss_damage=params['dmg_on_miss'], on_crit_pmf_expr=custom_crit_expr)
                        total_pmf = du.autoconvolve_pmf(single_action_pmf, params['num_actions'])
                        final_pmf = du.apply_resistance_vulnerability(total_pmf, params['enemy_resistance'])
                        st.session_state.current_calculation = {'pmf': final_pmf, 'params': params}
                        st.session_state.current_pmf = final_pmf

    # --- SAVING THROW FORM ---
    if action_type == "Saving Throw":
        with st.form(key='saving_throw_form'):
            st.text_input("Saving Throw Roll", "adv(1d20)+5", key="save_roll_string")
            with st.expander("**Save Details**", expanded=True):
                st.number_input("Saving Throw DC", 1, 30, 15, key="save_dc")
                st.radio("Resistance/Vulnerability", ["Neither", "Resistant", "Vulnerable"], horizontal=True, key="save_resistance")
                st.checkbox("Target has Evasion", key="has_evasion")
                st.text_input("Damage on Failed Save", "8d6", key="fail_dmg_string")
                
                save_success_behavior = st.radio(
                    "On Successful Save:",
                    ["No Damage", "Half Damage", "Custom"],
                    horizontal=True,
                    key="save_success_behavior"
                )
                if save_success_behavior == "Custom":
                    st.text_input("Damage on Successful Save", "4d6", key="succ_dmg_string")

            with st.expander("**Scenario**"):
                st.number_input("Number of Identical Actions", 1, 10, 1, key="num_actions")
            
            if st.session_state.editing_action_index is not None:
                if st.form_submit_button("Update Action"):
                    params = get_action_params(action_type)
                    if params:
                        succ_dmg_expr = params['succ_dmg_string'] if params['save_success_behavior'] == "Custom" else ""
                        base_save_pmf = dndu.get_save_damage_distribution(
                            save_dc=params['save_dc'],
                            save_roll_string=params['save_roll_string'],
                            on_fail_pmf_expr=params['fail_dmg_string'],
                            on_succeed_pmf_expr=succ_dmg_expr,
                            save_success_behavior=params['save_success_behavior'],
                            has_evasion=params['has_evasion']
                        )
                        final_save_pmf = du.apply_resistance_vulnerability(base_save_pmf, params['save_resistance'])
                        final_pmf = du.autoconvolve_pmf(final_save_pmf, params['num_actions'])
                        st.session_state.multi_actions[st.session_state.editing_action_index]['pmf'] = final_pmf
                        st.session_state.multi_actions[st.session_state.editing_action_index]['params'] = params
                        calculate_multi_action_pmf()
                        st.session_state.editing_action_index = None
                        st.rerun()
                if st.form_submit_button("Cancel"):
                    st.session_state.editing_action_index = None
                    st.rerun()
            else:
                if st.form_submit_button("Calculate"):
                    params = get_action_params(action_type)
                    if params:
                        succ_dmg_expr = params['succ_dmg_string'] if params['save_success_behavior'] == "Custom" else ""
                        base_save_pmf = dndu.get_save_damage_distribution(
                            save_dc=params['save_dc'],
                            save_roll_string=params['save_roll_string'],
                            on_fail_pmf_expr=params['fail_dmg_string'],
                            on_succeed_pmf_expr=succ_dmg_expr,
                            save_success_behavior=params['save_success_behavior'],
                            has_evasion=params['has_evasion']
                        )
                        final_save_pmf = du.apply_resistance_vulnerability(base_save_pmf, params['save_resistance'])
                        final_pmf = du.autoconvolve_pmf(final_save_pmf, params['num_actions'])
                        st.session_state.current_calculation = {'pmf': final_pmf, 'params': params}
                        st.session_state.current_pmf = final_pmf

    with st.expander("**Dice String Syntax**"):
        st.markdown(
            """- **Dice:** `1d20`, `2d6+3`
- **Advantage/Disadvantage/Elven Accuracy:** `adv(1d20)`, `disadv(1d20)` , `ea(1d20)`
- **Reroll:** `2d6r1`
- **Minimum:** `2d6m3`"""
            )

# --- Results Panel ---
with main_cols[1]:
    st.header("Results")
    
    # Display options
    st.checkbox("Show Current Calculation", True, key="show_current")
    view_mode = "Off"
    if st.session_state.multi_actions:
        view_mode = st.radio("Action Sequence Display", ["Off", "Combined", "Individual"], horizontal=True)

    # Determine which PMFs to display
    all_dfs = []
    if st.session_state.current_calculation and st.session_state.show_current:
        all_dfs.append(pmf_to_df(st.session_state.current_calculation['pmf'], "Current"))

    if view_mode == "Combined":
        all_dfs.append(pmf_to_df(st.session_state.multi_action_pmf, "Multi-Action"))
    elif view_mode == "Individual":
        for action in st.session_state.multi_actions:
            all_dfs.append(pmf_to_df(action['pmf'], action['name']))

    # Add comparison data if any exists
    for c in st.session_state.comparison_data:
        all_dfs.append(pmf_to_df(c['pmf'], c['name']))

    if all_dfs:
        plot_df = pd.concat(all_dfs).reset_index(drop=True)
        x_axis_title = "Damage" # Simplified for now

        plot_type = st.radio("Plot Type:", ["Probability (PMF)", "Cumulative (CDF)"], horizontal=True, label_visibility="collapsed")

        if plot_type == "Probability (PMF)":
            chart = alt.Chart(plot_df).mark_bar().encode(
                x=alt.X('Value:Q', title=x_axis_title, axis=alt.Axis(tickMinStep=1, grid=False)),
                y=alt.Y('Probability:Q', axis=alt.Axis(format='%')),
                color='Comparison:N',
                tooltip=['Value', alt.Tooltip('Probability', format='.2%')]
            ).properties(height=400).interactive()
        else: # CDF
            plot_df_cdf = plot_df[plot_df["Value"] > 0].copy()
            plot_df_cdf["tooltip_txt"] = plot_df_cdf.apply(
                lambda row: f"{row['CDF']:.1%} chance for at least {row['Value']} damage",
                axis=1
            )
            chart = (
                alt.Chart(plot_df_cdf)
                   .mark_line(point=True)
                   .encode(
                       x=alt.X("Value:Q", title=x_axis_title,
                               scale=alt.Scale(zero=False)),
                       y=alt.Y("CDF:Q", title=f"P({x_axis_title} ≥ X)",
                               axis=alt.Axis(format="%")),
                       color="Comparison:N",
                       tooltip=alt.Tooltip("tooltip_txt:N", title=None)
                   )
                   .properties(height=400)
                   .interactive()   
            ).properties(height=400).interactive()
        
        st.altair_chart(chart, use_container_width=True)

        dpr_cols = st.columns(len(all_dfs))
        for i, df in enumerate(all_dfs):
            avg = np.sum(df["Value"] * df["Probability"])
            dpr_cols[i].metric(f"Avg. {x_axis_title}: {df.iloc[0]['Comparison']}", f"{avg:.2f}")

        with st.expander("**Compare & Export Results**"):
            st.text_input("Name for comparison:", f"Scenario {len(st.session_state.comparison_data) + 1}", key="comp_name")
            if st.button("Save for Comparison"):
                # Determine what to save based on view
                pmf_to_save = None
                if view_mode == "Combined":
                    pmf_to_save = st.session_state.multi_action_pmf
                elif st.session_state.current_calculation and st.session_state.show_current:
                    pmf_to_save = st.session_state.current_calculation['pmf']
                
                if pmf_to_save:
                    st.session_state.comparison_data.append({'name': st.session_state.comp_name, 'pmf': pmf_to_save})
                else:
                    st.warning("Nothing to save. Please calculate something or select a combined action.")

            if st.button("Clear Comparisons"):
                st.session_state.comparison_data = []
            
            # Export/Import
            st.download_button("Download Comparison Data", json.dumps(st.session_state.comparison_data), "dnd_comparison_data.json", "application/json")
            uploaded_file = st.file_uploader("Upload Comparison Data", type=['json'])
            if uploaded_file is not None:
                try:
                    st.session_state.comparison_data = json.load(uploaded_file)
                    st.success("Comparison data loaded!")
                except Exception as e:
                    st.error(f"Failed to load data: {e}")
