import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import sys, os

import dice_utils as du
import dnd_utils as dndu

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
st.set_page_config(layout="wide")

st.title("D&D Damage Calculator")

# --- Session State Initialization ---
def init_session_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

init_session_state('action_library', {})
init_session_state('editing_action_name', None)

# --- Decorated Edit Dialog ---
@st.dialog("Edit Action")
def edit_action_dialog(action_name):
    action = st.session_state.action_library[action_name]
    action_type = action['action_type']

    new_name = st.text_input("Action Name",
                             value=action_name,
                             key="edit_action_name")
    st.text(f"Action Type: {action_type}")

    if action_type == "Dice Roll":
        st.text_input("Dice String",
                      value=action.get('dice_roll_string', ''),
                      key="dice_roll_string_edit")

    elif action_type == "Attack Roll":
        st.text_input("Attack Roll String",
                      value=action.get('attack_roll_string', ''),
                      key="attack_roll_string_edit")
        st.number_input("Enemy AC", 1, 30,
                        value=action.get('enemy_ac', 15),
                        key="enemy_ac_edit")
        st.radio("Resistance/Vulnerability",
                 ["Neither", "Resistant", "Vulnerable"],
                 index=["Neither", "Resistant", "Vulnerable"]
                       .index(action.get('enemy_resistance', 'Neither')),
                 horizontal=True,
                 key="enemy_resistance_edit")
        st.text_input("Damage (on hit)",
                      value=action.get('dmg_string', ''),
                      key="dmg_string_edit")
        st.number_input("Crit on d20 roll of...", 1, 20,
                        value=action.get('crit_range', 20),
                        key="crit_range_edit")
        use_custom = st.checkbox("Custom damage on crit",
                                 value=action.get('use_custom_crit', False),
                                 key="use_custom_crit_edit")
        if use_custom:
            default_crit = du.get_doubled_dice_string(
                st.session_state.dmg_string_edit
            )
            st.text_input("Damage on Crit",
                          value=action.get('custom_crit_string', default_crit),
                          key="custom_crit_string_edit")
        st.number_input("Flat Damage on Miss", 0,
                        value=action.get('dmg_on_miss', 0),
                        key="dmg_on_miss_edit")

    else:  # Saving Throw
        st.text_input("Saving Throw Roll",
                      value=action.get('save_roll_string', ''),
                      key="save_roll_string_edit")
        st.number_input("Saving Throw DC", 1, 30,
                        value=action.get('save_dc', 15),
                        key="save_dc_edit")
        st.radio("Resistance/Vulnerability",
                 ["Neither", "Resistant", "Vulnerable"],
                 index=["Neither", "Resistant", "Vulnerable"]
                       .index(action.get('save_resistance', 'Neither')),
                 horizontal=True,
                 key="save_resistance_edit")
        st.checkbox("Target has Evasion",
                    value=action.get('has_evasion', False),
                    key="has_evasion_edit")
        st.text_input("Damage on Failed Save",
                      value=action.get('fail_dmg_string', ''),
                      key="fail_dmg_string_edit")
        save_behav = st.radio("On Successful Save:",
                              ["No Damage", "Half Damage", "Custom"],
                              index=["No Damage","Half Damage","Custom"]
                                    .index(action.get('save_success_behavior','No Damage')),
                              horizontal=True,
                              key="save_success_behavior_edit")
        if save_behav == "Custom":
            st.text_input("Damage on Successful Save",
                          value=action.get('succ_dmg_string',''),
                          key="succ_dmg_string_edit")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Update Action", key="update_action_btn"):
            edited = {'action_type': action_type}
            if action_type == "Dice Roll":
                edited['dice_roll_string'] = st.session_state.dice_roll_string_edit
            elif action_type == "Attack Roll":
                edited.update({
                    'attack_roll_string': st.session_state.attack_roll_string_edit,
                    'enemy_ac':           st.session_state.enemy_ac_edit,
                    'enemy_resistance':   st.session_state.enemy_resistance_edit,
                    'dmg_string':         st.session_state.dmg_string_edit,
                    'crit_range':         st.session_state.crit_range_edit,
                    'use_custom_crit':    st.session_state.use_custom_crit_edit,
                    'custom_crit_string': st.session_state.get('custom_crit_string_edit'),
                    'dmg_on_miss':        st.session_state.dmg_on_miss_edit
                })
            else:
                edited.update({
                    'save_roll_string':      st.session_state.save_roll_string_edit,
                    'save_dc':               st.session_state.save_dc_edit,
                    'save_resistance':       st.session_state.save_resistance_edit,
                    'has_evasion':           st.session_state.has_evasion_edit,
                    'fail_dmg_string':       st.session_state.fail_dmg_string_edit,
                    'save_success_behavior': st.session_state.save_success_behavior_edit,
                    'succ_dmg_string':       st.session_state.get('succ_dmg_string_edit')
                })

            if new_name != action_name:
                del st.session_state.action_library[action_name]
            st.session_state.action_library[new_name] = edited
            st.session_state.editing_action_name = None
            st.rerun()

    with c2:
        if st.button("Cancel", key="cancel_edit_btn"):
            st.session_state.editing_action_name = None
            st.rerun()


# --- Sidebar: Create New Action ---
st.sidebar.header("Create Action")
with st.sidebar.expander("**Dice String Syntax**"):
        st.markdown(
            """- **Dice:** `1d20`, `2d6+3`
- **Advantage/Disadvantage/Elven Accuracy:** `adv(1d20)`, `disadv(1d20)` , `ea(1d20)`
- **Reroll:** `2d6r1`
- **Minimum:** `2d6m3`"""
            )
with st.sidebar.expander("New Action", expanded=True):
    action_type = st.radio("Action Type",
                           ["Dice Roll", "Attack Roll", "Saving Throw"],
                           key="action_type_selector")

    def save_new_action():
        name = st.session_state.new_action_name.strip()
        if not name:
            st.sidebar.warning("Enter an action name.")
            return
        if name in st.session_state.action_library:
            st.sidebar.warning("Name already exists.")
            return
        params = {}
        if action_type == "Dice Roll":
            params = {'action_type': "Dice Roll",
                      'dice_roll_string': st.session_state.dice_roll_string}
        elif action_type == "Attack Roll":
            params = {
                'action_type':       "Attack Roll",
                'attack_roll_string': st.session_state.attack_roll_string,
                'enemy_ac':           st.session_state.enemy_ac,
                'enemy_resistance':   st.session_state.enemy_resistance,
                'dmg_string':         st.session_state.dmg_string,
                'crit_range':         st.session_state.crit_range,
                'use_custom_crit':    st.session_state.use_custom_crit,
                'custom_crit_string': st.session_state.get('custom_crit_string', None),
                'dmg_on_miss':        st.session_state.dmg_on_miss
            }
        else:
            params = {
                'action_type':          "Saving Throw",
                'save_roll_string':     st.session_state.save_roll_string,
                'save_dc':              st.session_state.save_dc,
                'save_resistance':      st.session_state.save_resistance,
                'has_evasion':          st.session_state.has_evasion,
                'fail_dmg_string':      st.session_state.fail_dmg_string,
                'save_success_behavior': st.session_state.save_success_behavior,
                'succ_dmg_string':      st.session_state.get('succ_dmg_string', None)
            }

        st.session_state.action_library[name] = params
        st.sidebar.success(f"Saved '{name}'")
        st.session_state.new_action_name = ""

    if action_type == "Dice Roll":
        st.text_input("Dice String", "1d4", key="dice_roll_string")
    elif action_type == "Attack Roll":
        st.text_input("Attack Roll String", "adv(1d20) + 5",
                      key="attack_roll_string")
        st.number_input("Enemy AC", 1, 30, 15, key="enemy_ac")
        st.radio("Resistance/Vulnerability",
                 ["Neither","Resistant","Vulnerable"],
                 horizontal=True, key="enemy_resistance")
        st.text_input("Damage (on hit)", "1d8+3", key="dmg_string")
        st.number_input("Crit on d20 roll of...", 1, 20, 20, key="crit_range")
        st.checkbox("Custom damage on crit", key="use_custom_crit")
        if st.session_state.use_custom_crit:
            st.text_input("Damage on Crit",
                          du.get_doubled_dice_string(
                              st.session_state.dmg_string
                          ),
                          key="custom_crit_string")
        st.number_input("Flat Damage on Miss", 0, key="dmg_on_miss")
    else:
        st.text_input("Saving Throw Roll", "adv(1d20)+5",
                      key="save_roll_string")
        st.number_input("Saving Throw DC", 1, 30, 15, key="save_dc")
        st.radio("Resistance/Vulnerability",
                 ["Neither","Resistant","Vulnerable"],
                 horizontal=True, key="save_resistance")
        st.checkbox("Target has Evasion", key="has_evasion")
        st.text_input("Damage on Failed Save", "8d6",
                      key="fail_dmg_string")
        st.radio("On Successful Save:",
                 ["No Damage","Half Damage","Custom"],
                 horizontal=True, key="save_success_behavior")
        if st.session_state.save_success_behavior == "Custom":
            st.text_input("Damage on Successful Save", "4d6",
                          key="succ_dmg_string")

    st.text_input("Action Name", key="new_action_name")
    st.button("Save Action", on_click=save_new_action, key="save_new_btn")

# --- Main Panel ---
mode1, mode2, mode3 = st.tabs([
    "Action Library", "Action Sequences", "Build Comparisons"
])

with mode1:
    # 1) Compute DPR (average damage) for each saved action
    action_dprs = {}
    for name, params in st.session_state.action_library.items():
        pmf = {}
        if params['action_type'] == "Dice Roll":
            pmf = du.parse_and_calculate_pmf(params['dice_roll_string'])
        elif params['action_type'] == "Attack Roll":
            crit_expr = params.get('custom_crit_string') if params.get('use_custom_crit') else ""
            pmf = dndu.get_full_damage_distribution(
                d20_string=params['attack_roll_string'],
                ac=params['enemy_ac'],
                crit_range=[params['crit_range'], 20],
                on_hit_pmf_expr=params['dmg_string'],
                on_miss_damage=params['dmg_on_miss'],
                on_crit_pmf_expr=crit_expr
            )
            pmf = du.apply_resistance_vulnerability(pmf, params['enemy_resistance'])
        else:  # Saving Throw
            succ_expr = params.get('succ_dmg_string') if params.get('save_success_behavior') == "Custom" else ""
            pmf = dndu.get_save_damage_distribution(
                save_dc=params['save_dc'],
                save_roll_string=params['save_roll_string'],
                on_fail_pmf_expr=params['fail_dmg_string'],
                on_succeed_pmf_expr=succ_expr,
                save_success_behavior=params['save_success_behavior'],
                has_evasion=params['has_evasion']
            )
            pmf = du.apply_resistance_vulnerability(pmf, params['save_resistance'])

        action_dprs[name] = np.sum([d * p for d, p in pmf.items()]) if pmf else 0

    # 2) Plotting pane (only if user has selected at least one card)
    selected = {
        n: p
        for n, p in st.session_state.action_library.items()
        if st.session_state.get(f"action_select_{n}", False)
    }

    if selected:
        dfs = []
        for name, params in selected.items():
            if params['action_type'] == "Dice Roll":
                pmf = du.parse_and_calculate_pmf(params['dice_roll_string'])
            elif params['action_type'] == "Attack Roll":
                crit_expr = params.get('custom_crit_string') if params.get('use_custom_crit') else ""
                pmf = dndu.get_full_damage_distribution(
                    d20_string=params['attack_roll_string'],
                    ac=params['enemy_ac'],
                    crit_range=[params['crit_range'], 20],
                    on_hit_pmf_expr=params['dmg_string'],
                    on_miss_damage=params['dmg_on_miss'],
                    on_crit_pmf_expr=crit_expr
                )
                pmf = du.apply_resistance_vulnerability(pmf, params['enemy_resistance'])
            else:
                succ_expr = params.get('succ_dmg_string') if params.get('save_success_behavior') == "Custom" else ""
                pmf = dndu.get_save_damage_distribution(
                    save_dc=params['save_dc'],
                    save_roll_string=params['save_roll_string'],
                    on_fail_pmf_expr=params['fail_dmg_string'],
                    on_succeed_pmf_expr=succ_expr,
                    save_success_behavior=params['save_success_behavior'],
                    has_evasion=params['has_evasion']
                )
                pmf = du.apply_resistance_vulnerability(pmf, params['save_resistance'])

            df = pd.DataFrame(pmf.items(), columns=["Damage", "Probability"])
            df["Action"] = name
            dfs.append(df)

        plot_df = pd.concat(dfs)
           # … after building plot_df …

        # Plot options row
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            st.write("**Plot Type**")
        with c2:
            plot_type = st.radio(
                "Plot Type",
                ["Probability (PMF)", "Minimum Damage Probability"],
                horizontal=True,
                key="plot_type",
                label_visibility="collapsed"
            )
        with c3:
            show_avg = st.checkbox("Show Average Lines", True)

        base = alt.Chart(plot_df)

        if plot_type == "Probability (PMF)":
            chart = base.mark_bar().encode(
                x=alt.X("Damage:Q", axis=alt.Axis(tickMinStep=1, grid=False)),
                y=alt.Y("Probability:Q", axis=alt.Axis(format="%")),
                color="Action:N",
                tooltip=["Action", "Damage", alt.Tooltip("Probability", format=".2%")],
            ).properties(height=400).interactive()

        else:  # Minimum Damage Probability
            # — your original CDF/min‐damage code preserved here —
            min_dmg_df = plot_df.sort_values("Damage").reset_index(drop=True)
            min_dmg_df["CDF"] = (
                min_dmg_df.groupby("Action")["Probability"].cumsum()
            )
            min_dmg_df["MinDamageProb"] = (
                1
                - min_dmg_df["CDF"]
                + min_dmg_df["Probability"]
            )
            # only positive damage points
            min_dmg_df = min_dmg_df[min_dmg_df["Damage"] > 0]
            # build a custom tooltip string
            min_dmg_df["tooltip_text"] = min_dmg_df.apply(
                lambda row: f"{row['MinDamageProb']:.1%} chance for at least {row['Damage']} damage",
                axis=1,
            )

            chart = (
                alt.Chart(min_dmg_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Damage:Q", scale=alt.Scale(zero=False)),
                    y=alt.Y(
                        "MinDamageProb:Q",
                        title="P(Damage ≥ X)",
                        axis=alt.Axis(format="%"),
                    ),
                    color="Action:N",
                    tooltip=alt.Tooltip("tooltip_text:N", title="Min Damage Prob"),
                )
                .properties(height=400)
                .interactive()
            )

        # overlay average‐damage rule if desired
        if show_avg:
            avg_df = (
                plot_df.groupby("Action")
                .apply(lambda g: pd.Series({"avg": (g["Damage"] * g["Probability"]).sum()}))
                .reset_index()
            )
            avg_rule = (
                alt.Chart(avg_df)
                .mark_rule(strokeDash=[4, 4])
                .encode(
                    x="avg:Q",
                    color="Action:N",
                    tooltip=[
                        alt.Tooltip("Action:N"),
                        alt.Tooltip("avg:Q", title="Average Damage", format=".2f"),
                    ],
                )
            )
            chart = alt.layer(chart, avg_rule)

        st.altair_chart(chart, use_container_width=True)

    else:
        st.info("Select one or more actions below to plot their distributions. To create new actions, use side panel.")

    # 3) Search & Sort
    search = st.text_input("Search Actions", key="search_actions")
    s1, s2 = st.columns([3, 2])
    with s1:
        sort_by = st.selectbox("Sort by", ["Name", "Average Damage"], key="sort_by")
    with s2:
        order = st.radio("Order", ["Ascending", "Descending"], horizontal=True, key="sort_order")

    # 4) Styled Card Grid (5 across)
    filtered = {
        n: p
        for n, p in st.session_state.action_library.items()
        if search.lower() in n.lower()
    }
    names = sorted(
        filtered.keys(),
        key=lambda n: (action_dprs[n] if sort_by == "Average Damage" else n),
        reverse=(order == "Descending"),
    )

    for i in range(0, len(names), 5):
        cols = st.columns(5)
        for j, name in enumerate(names[i : i + 5]):
            params = filtered[name]
            avg = action_dprs.get(name, 0)
            is_sel = st.session_state.get(f"action_select_{name}", False)
            bg = "#0068C9" if is_sel else "#222222"
            fg = "#FFF" if is_sel else "#EEE"

            # Per-card CSS to style only this column’s button
            css = f"""
            <style>
            div[data-testid="stVerticalBlock"] > div:nth-child({j+1}) > div > button[data-testid^="stButton"] {{
                background-color: {bg};
                color: {fg};
                border: 1px solid #444;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 8px;
                text-align: left;
                white-space: pre-wrap;
            }}
            </style>
            """
            cols[j].markdown(css, unsafe_allow_html=True)

            # Main card button with multiline label
            label = f"**{name}**\n\n*{params['action_type']}*  Avg: **{avg:.2f}**"
            if cols[j].button(label, key=f"select_card_{name}"):
                st.session_state[f"action_select_{name}"] = not is_sel
                st.rerun()

            # Edit & Delete icons
            ecol, dcol = cols[j].columns(2)
            if ecol.button("✏️", key=f"edit_{name}", help="Edit this action"):
                st.session_state.editing_action_name = name
                st.rerun()
            if dcol.button("🗑️", key=f"delete_{name}", help="Delete this action"):
                del st.session_state.action_library[name]
                st.rerun()

    # 5) Invoke the edit dialog when requested
    if st.session_state.editing_action_name:
        edit_action_dialog(st.session_state.editing_action_name)



with mode2:
    st.header("Action Sequences")
    st.info("Under construction.")

with mode3:
    st.header("Build Comparisons")
    st.info("Under construction.")
