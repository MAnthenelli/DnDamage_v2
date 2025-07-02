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

# --- Helper Functions ---
def pmf_to_df(pmf, name="current"):
    if not pmf: return pd.DataFrame()
    df = pd.DataFrame(list(pmf.items()), columns=["Value", "Probability"])
    df["Comparison"] = name
    df = df.sort_values("Value").reset_index(drop=True)
    df["CDF"] = 1 - df["Probability"].cumsum() + df["Probability"]
    return df

# --- UI Rendering ---
st.title("D&D Dice & Damage Calculator")

main_cols = st.columns([0.45, 0.55])

with main_cols[0]:
    st.header("Controls")
    action_type = st.radio("Select Action Type:", ["Dice Roll", "Attack Roll", "Saving Throw"], horizontal=True)

    # --- DICE ROLL FORM ---
    if action_type == "Dice Roll":
        with st.form(key='dice_roll_form'):
            st.text_input("Dice String", "1d4m2", key="dice_roll_string")
            submit_button = st.form_submit_button("Calculate")
            if submit_button:
                st.session_state.current_pmf = du.parse_and_calculate_pmf(st.session_state.dice_roll_string)

    # --- ATTACK ROLL FORM ---
    if action_type == "Attack Roll":
        with st.form(key='attack_roll_form'):
            st.text_input("Attack Roll String", "adv(1d20) + 5", key="attack_roll_string")
            with st.expander("**Target**", expanded=True):
                st.number_input("Armor Class", 1, 30, 15, key="enemy_ac")
                st.radio("Resistance/Vulnerability", ["Neither", "Resistant", "Vulnerable"], horizontal=True, key="enemy_resistance")
            with st.expander("**Damage**", expanded=True):
                st.text_input("Damage (on hit)", "1d8+3", key="dmg_string")
                st.slider("Crit on d20 roll of...", 1, 20, 20, key="crit_range")
                if st.checkbox("Add extra dice on crit", key="use_brutal_crit"):
                    st.text_input("Additional Dice on Crit", "1d6", key="brutal_crit_string")
                st.number_input("Flat Damage on Miss", 0, key="dmg_on_miss")
            with st.expander("**Scenario**"):
                st.number_input("Number of Identical Actions", 1, 10, 1, key="num_actions")
            submit_button = st.form_submit_button("Calculate")
            if submit_button:
                brutal_crit_expr = st.session_state.brutal_crit_string if st.session_state.use_brutal_crit else ""
                single_action_pmf = dndu.get_full_damage_distribution(
                    d20_string=st.session_state.attack_roll_string, ac=st.session_state.enemy_ac,
                    crit_range=[st.session_state.crit_range, 20], on_hit_pmf_expr=st.session_state.dmg_string,
                    on_miss_damage=st.session_state.dmg_on_miss, brutal_crit_dice_expr=brutal_crit_expr)
                total_pmf = du.autoconvolve_pmf(single_action_pmf, st.session_state.num_actions)
                st.session_state.current_pmf = du.apply_resistance_vulnerability(total_pmf, st.session_state.enemy_resistance)

    # --- SAVING THROW FORM ---
    if action_type == "Saving Throw":
        with st.form(key='saving_throw_form'):
            st.text_input("Saving Throw Modifier String", "1d20 +3", key="save_mod_string")
            with st.expander("**Save Details**", expanded=True):
                st.slider("Saving Throw DC", 1, 30, 15, key="save_dc")
                st.text_input("Damage on Failed Save", "8d6", key="fail_dmg_string")
                st.text_input("Damage on Successful Save", "4d6", key="succ_dmg_string")
                st.radio("Advantage on Save?", ["Straight", "Advantage", "Disadvantage"], horizontal=True, key="adv_save")
            with st.expander("**Scenario**"):
                st.number_input("Number of Identical Actions", 1, 10, 1, key="num_actions")
            submit_button = st.form_submit_button("Calculate")
            if submit_button:
                single_action_pmf = dndu.get_save_damage_distribution(
                    save_dc=st.session_state.save_dc, save_mod_string=st.session_state.save_mod_string,
                    on_fail_pmf_expr=st.session_state.fail_dmg_string, on_succeed_pmf_expr=st.session_state.succ_dmg_string,
                    adv_disadv=st.session_state.adv_save.lower())
                st.session_state.current_pmf = du.autoconvolve_pmf(single_action_pmf, st.session_state.num_actions)

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
    if st.session_state.current_pmf:
        df_current = pmf_to_df(st.session_state.current_pmf, "Current")
        all_dfs = [df_current] + [pmf_to_df(c['pmf'], c['name']) for c in st.session_state.comparison_data]
        plot_df = pd.concat(all_dfs).reset_index(drop=True)
        x_axis_title = "Damage" if action_type != "Dice Roll" else "Value"

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
            st.text_input("Name for current calculation:", f"Scenario {len(st.session_state.comparison_data) + 1}", key="comp_name")
            if st.button("Save for Comparison"):
                st.session_state.comparison_data.append({'name': st.session_state.comp_name, 'pmf': st.session_state.current_pmf})
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