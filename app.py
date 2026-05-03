from html import escape
from time import sleep

import streamlit as st

from shadow_bout import (
    Janken,
    JankenResult,
    Phase,
    RandomStrategy,
    RoundOutcome,
    Side,
    calculate_final_score,
    continue_round_effect_step,
    load_deck,
    proceed_to_next,
    resolve_npc_pending_effects_stepwise,
    resume_round_effect_stepwise,
    select_card_stepwise,
    start_game,
)
from shadow_bout.effects import calculate_effective_point

# Constants
CARD_IDS = [
    "card_26",
    "card_24",
    "card_14",
    "card_11",
    "card_25",
    "card_15",
    "card_38",
    "card_02",
    "card_08",
    "card_06",
    "card_44",
    "card_50",
    "card_05",
]

JANKEN_ICONS = {Janken.ROCK: "✊", Janken.SCISSORS: "✌️", Janken.PAPER: "✋"}

st.set_page_config(page_title="Shadow Bout v0.2", layout="wide")


def render_janken_result():
    st.caption("じゃんけん")


def render_card_info(card):
    return f"{card.name} {JANKEN_ICONS.get(card.janken, '')}{card.base_point}"


def render_card_option_label(card):
    description = card.effect.description if card.effect else "（効果なし）"
    return f"{render_card_info(card)}｜{description}"


def render_card_detail(card):
    with st.container(border=True):
        st.markdown(f"**{render_card_info(card)}**")
        if card.effect:
            st.caption(card.effect.description)
        else:
            st.caption("（効果なし）")


def render_battle_card(card, pt_str, *, is_highlighted=False):
    description = card.effect.description if card.effect else "（効果なし）"
    border_color = "#f2b84b" if is_highlighted else "#d4d6da"
    background_color = "#fff8e6" if is_highlighted else "#ffffff"
    shadow = "0 0 0 2px rgba(242, 184, 75, 0.18)" if is_highlighted else "none"
    safe_description = escape(description).replace("\n", "<br>")

    st.markdown(
        f"""
        <div style="
            border: 2px solid {border_color};
            border-radius: 8px;
            background: {background_color};
            box-shadow: {shadow};
            padding: 1rem;
            min-height: 118px;
        ">
            <p style="font-weight: 700; font-size: 1.15rem; margin: 0 0 1rem;">
                {escape(card.name)} {JANKEN_ICONS.get(card.janken, "")}{escape(pt_str)}
            </p>
            <p style="color: #80838b; line-height: 1.65; margin: 0;">
                {safe_description}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_selectable_card(card, *, is_selected, key):
    description = card.effect.description if card.effect else "（効果なし）"
    prefix = "選択中\n\n" if is_selected else ""
    label = f"{prefix}{render_card_info(card)}\n\n{description}"
    return st.button(
        label,
        key=key,
        type="primary" if is_selected else "secondary",
        use_container_width=True,
    )


def find_card_by_id(cards, card_id):
    return next((card for card in cards if card.id == card_id), None)


def card_id_options(cards):
    labels = {card.id: render_card_option_label(card) for card in cards}
    return list(labels), labels


def render_footer_links():
    st.markdown("---")
    st.caption("関連リンク")
    st.markdown(
        """
        - [陰界戦戯とは](https://x.com/imasml_theater/status/2047601441863282705)
        - [もっと知る（ミリシタをダウンロード）](https://millionlive-theaterdays.idolmaster-official.jp/)
        - [このアプリのソースコード](https://github.com/ftnext/millionlive-shadow-bout)
        """
    )


def submit_effect_choice(game_state, choice):
    before_logs = game_state.battle_log
    state = resume_round_effect_stepwise(game_state, choice)
    state = resolve_npc_pending_effects_stepwise(state, st.session_state.npc_strategy)
    if (
        game_state.pending_effect_context
        and game_state.pending_effect_context.effect == "reorder"
    ):
        clear_reorder_widget_state()
    queue_effect_toasts(before_logs, state.battle_log)
    st.session_state.game_state = state
    st.rerun()


def continue_effect_resolution(game_state, *, auto_rerun=False):
    before_logs = game_state.battle_log
    state = continue_round_effect_step(game_state)
    state = resolve_npc_pending_effects_stepwise(state, st.session_state.npc_strategy)
    queue_effect_toasts(before_logs, state.battle_log)
    st.session_state.game_state = state
    if auto_rerun:
        show_pending_toasts()
        sleep(1.0)
    st.rerun()


def effect_log_entries(logs):
    markers = ("効果発動", "の効果:", "copy_effect")
    return [log for log in logs if any(marker in log for marker in markers)]


def queue_effect_toasts(before_logs, after_logs):
    before_count = len(before_logs)
    new_effect_logs = effect_log_entries(after_logs[before_count:])
    if new_effect_logs:
        st.session_state.pending_toasts = (
            st.session_state.get("pending_toasts", []) + new_effect_logs
        )


def show_pending_toasts():
    pending_toasts = st.session_state.get("pending_toasts", [])
    for message in pending_toasts:
        st.toast(message, icon="✨")
    if pending_toasts:
        st.session_state.pending_toasts = []


def clear_reorder_widget_state():
    for key in list(st.session_state.keys()):
        if key.startswith("reorder_deck_cards_"):
            del st.session_state[key]


def side_label(side):
    return "あなた" if side == Side.PLAYER else "NPC"


def render_effect_resolution_panel(game_state):
    st.markdown("---")
    st.markdown("#### ── 戦具効果の解決 ──")

    latest_effect_logs = effect_log_entries(game_state.battle_log)
    if latest_effect_logs:
        st.caption(latest_effect_logs[-1])

    if game_state.effect_queue:
        side, card = game_state.effect_queue[0]
        st.info(f"{side_label(side)}の{card.name}を解決中...")
        render_card_detail(card)
        continue_effect_resolution(game_state, auto_rerun=True)
        return

    st.info("ポイント比較へ進みます。")
    continue_effect_resolution(game_state, auto_rerun=True)


def render_known_npc_hand(game_state):
    persistent_cards = [
        card
        for card in game_state.npc.hand
        if card.id in game_state.npc.revealed_card_ids
    ]

    if persistent_cards:
        st.caption("公開中のNPC手札")
        cols = st.columns(len(persistent_cards))
        for i, card in enumerate(persistent_cards):
            with cols[i]:
                render_card_detail(card)


def render_pending_effect_form(game_state):
    ctx = game_state.pending_effect_context
    if ctx is None:
        st.info("効果解決を続行します。")
        if st.button("次へ", type="primary", use_container_width=True):
            submit_effect_choice(game_state, None)
        return

    if ctx.side == Side.NPC:
        st.info("NPCが効果を選択しています。")
        if st.button("NPCの選択を解決", type="primary", use_container_width=True):
            st.session_state.game_state = resolve_npc_pending_effects_stepwise(
                game_state, st.session_state.npc_strategy
            )
            st.rerun()
        return

    player = game_state.player

    if ctx.effect == "choose":
        variant = ctx.payload.get("choose_variant")
        if variant == "yuriko_return_cards" and ctx.step == 1:
            return_count = int(ctx.payload.get("return_count", 0))
            options, labels = card_id_options(player.hand)
            selected = st.multiselect(
                f"山札の下へ戻す手札を{return_count}枚選択",
                options,
                format_func=lambda card_id: labels[card_id],
                max_selections=return_count,
                key="choose_return_cards",
            )
            is_ready = len(selected) == return_count
            if not is_ready:
                st.caption(f"{return_count}枚ちょうど選んでください。")
            if st.button(
                "戻す",
                type="primary",
                disabled=not is_ready,
                use_container_width=True,
            ):
                submit_effect_choice(game_state, ",".join(selected))
            return

        if variant == "yuriko_choose":
            choice = st.radio(
                "百合子の効果",
                ["gain_points", "draw_cards"],
                format_func=lambda value: {
                    "gain_points": "自分のポイント+3",
                    "draw_cards": "山札から2枚引き、手札2枚を山札の下へ戻す",
                }[value],
                horizontal=True,
            )
            if st.button("この効果を発動", type="primary", use_container_width=True):
                submit_effect_choice(game_state, choice)
            return

        if variant == "karen_choose":
            choice = st.radio(
                "可憐の効果",
                ["activate", "skip"],
                format_func=lambda value: {
                    "activate": "発動する（相手の公開を2ラウンド強制）",
                    "skip": "発動しない",
                }[value],
                horizontal=True,
            )
            if st.button("この効果を決定", type="primary", use_container_width=True):
                submit_effect_choice(game_state, choice)
            return

        st.info("このカードの選択効果には未対応です。")
        if st.button("次へ", type="primary", use_container_width=True):
            submit_effect_choice(game_state, None)
        return

    if ctx.effect == "copy_hand":
        options, labels = card_id_options(player.hand)
        if not options:
            st.info("選べる手札がありません。")
            if st.button("次へ", type="primary", use_container_width=True):
                submit_effect_choice(game_state, None)
            return

        choice = st.selectbox(
            "効果を発動する手札",
            options,
            format_func=lambda card_id: labels[card_id],
        )
        if st.button(
            "このカードの効果を発動", type="primary", use_container_width=True
        ):
            submit_effect_choice(game_state, choice)
        return

    if ctx.effect == "choose_multiple":
        options: list[str] = []
        if player.hand:
            options.append("discard_buff")
        if player.deck:
            options.append("draw_debuff")

        if not options:
            st.info("発動可能な効果がありません。")
            if st.button("次へ", type="primary", use_container_width=True):
                submit_effect_choice(game_state, "")
            return

        selected = st.multiselect(
            "海美の効果（1つまたは両方を選択）",
            options,
            format_func=lambda value: {
                "discard_buff": "手札1枚を捨て札に置いてポイント+5",
                "draw_debuff": "山札から1枚引いてポイント-2",
            }[value],
            key=f"choose_multiple_{game_state.round_number}_{ctx.card_id}_{ctx.side.value}",
        )
        is_ready = len(selected) > 0
        if not is_ready:
            st.caption("1つ以上選んでください。")
        if st.button(
            "この効果を決定",
            type="primary",
            disabled=not is_ready,
            use_container_width=True,
        ):
            submit_effect_choice(game_state, ",".join(selected))
        return

    if ctx.effect == "search_and_swap":
        mode = st.radio(
            "千鶴の効果",
            ["swap", "skip"],
            format_func=lambda value: {
                "swap": "手札と山札を交換する",
                "skip": "交換しない",
            }[value],
            horizontal=True,
        )
        if mode == "skip":
            if st.button("交換しない", type="primary", use_container_width=True):
                submit_effect_choice(game_state, None)
            return

        hand_options, hand_labels = card_id_options(player.hand)
        deck_options, deck_labels = card_id_options(player.deck)
        if not hand_options or not deck_options:
            st.info("交換できる手札または山札がありません。")
            if st.button("次へ", type="primary", use_container_width=True):
                submit_effect_choice(game_state, None)
            return

        hand_id = st.selectbox(
            "山札へ戻す手札",
            hand_options,
            format_func=lambda card_id: hand_labels[card_id],
        )
        deck_id = st.selectbox(
            "手札に加える山札",
            deck_options,
            format_func=lambda card_id: deck_labels[card_id],
        )
        if st.button("交換する", type="primary", use_container_width=True):
            submit_effect_choice(game_state, f"{hand_id}:{deck_id}")
        return

    if ctx.effect == "swap":
        mode = st.radio(
            "真の効果",
            ["swap", "skip"],
            format_func=lambda value: {
                "swap": "場のカードと手札を入れ替える",
                "skip": "入れ替えない",
            }[value],
            horizontal=True,
        )
        if mode == "skip":
            if st.button("入れ替えない", type="primary", use_container_width=True):
                submit_effect_choice(game_state, None)
            return

        options, labels = card_id_options(player.hand)
        if not options:
            st.info("入れ替えられる手札がありません。")
            if st.button("次へ", type="primary", use_container_width=True):
                submit_effect_choice(game_state, None)
            return

        choice = st.selectbox(
            "場に出す手札",
            options,
            format_func=lambda card_id: labels[card_id],
        )
        if st.button("入れ替える", type="primary", use_container_width=True):
            submit_effect_choice(game_state, choice)
        return

    if ctx.effect == "swap_opponent":
        opponent = game_state.npc if ctx.side == Side.PLAYER else game_state.player
        if not opponent.hand:
            st.info("相手の手札がないため入れ替えできません。")
            if st.button("次へ", type="primary", use_container_width=True):
                submit_effect_choice(game_state, None)
            return

        if ctx.step == 0:
            st.info("相手手札をランダムに1枚確認します。")
            if st.button("確認する", type="primary", use_container_width=True):
                submit_effect_choice(game_state, "reveal")
            return

        target_id = ctx.payload.get("target_id")
        target = next((card for card in opponent.hand if card.id == target_id), None)
        if target is None:
            st.warning("確認したカードが見つかりません。")
            if st.button("次へ", type="primary", use_container_width=True):
                submit_effect_choice(game_state, None)
            return

        st.write(f"確認したカード: **{target.name}**（{target.id}）")
        mode = st.radio(
            "可奈の効果",
            ["swap", "skip"],
            format_func=lambda value: {
                "swap": "このカードと相手の場カードを入れ替える",
                "skip": "入れ替えない",
            }[value],
            horizontal=True,
        )
        if st.button("決定", type="primary", use_container_width=True):
            submit_effect_choice(game_state, "swap" if mode == "swap" else None)
        return

    if ctx.effect == "removal":
        choice = st.radio(
            "ジュリアの効果",
            ["activate", "skip"],
            format_func=lambda value: {
                "activate": "発動する",
                "skip": "発動しない",
            }[value],
            horizontal=True,
        )
        if st.button("決定", type="primary", use_container_width=True):
            submit_effect_choice(game_state, choice)
        return

    if ctx.effect == "reorder":
        source_card = ctx.payload.get("source_card") if ctx.payload else None
        candidate_deck = list(player.deck)
        if source_card and all(card.id != source_card.id for card in candidate_deck):
            candidate_deck.append(source_card)

        options, labels = card_id_options(candidate_deck)
        if len(options) <= 1:
            st.info("並び替える山札がありません。")
            if st.button("次へ", type="primary", use_container_width=True):
                submit_effect_choice(game_state, None)
            return

        reorder_key = f"reorder_deck_cards_{game_state.round_number}_{ctx.card_id}_{ctx.side.value}"
        ordered_ids = st.multiselect(
            "山札の上から順にカードを選択",
            options,
            default=options,
            format_func=lambda card_id: labels[card_id],
            max_selections=len(options),
            key=reorder_key,
        )
        is_ready = len(ordered_ids) == len(options)
        if not is_ready:
            st.caption("山札の全カードを順番どおりに選択してください。")
        if st.button(
            "この順番にする",
            type="primary",
            disabled=not is_ready,
            use_container_width=True,
        ):
            submit_effect_choice(game_state, ",".join(ordered_ids))
        return

    if ctx.effect == "tutor_play":
        mode = st.radio(
            "麗花の効果",
            ["activate", "skip"],
            format_func=lambda value: {
                "activate": "発動する（このカードを山札に戻し、山札から1枚を場に出す）",
                "skip": "発動しない",
            }[value],
            horizontal=True,
        )
        if mode == "skip":
            if st.button("発動しない", type="primary", use_container_width=True):
                submit_effect_choice(game_state, "skip")
            return

        source_card = ctx.payload.get("source_card") if ctx.payload else None
        candidate_deck = list(player.deck)
        if source_card and all(card.id != source_card.id for card in candidate_deck):
            candidate_deck.append(source_card)

        options, labels = card_id_options(candidate_deck)
        if not options:
            st.info("山札がないため発動できません。")
            if st.button("次へ", type="primary", use_container_width=True):
                submit_effect_choice(game_state, "skip")
            return

        choice = st.selectbox(
            "場に出す山札のカード",
            options,
            format_func=lambda card_id: labels[card_id],
        )
        if st.button("このカードを場に出す", type="primary", use_container_width=True):
            submit_effect_choice(game_state, choice)
        return

    st.info("この効果は追加の入力なしで解決します。")
    if st.button("次へ", type="primary", use_container_width=True):
        submit_effect_choice(game_state, None)


def main():
    st.title("陰界戦戯（シャドウバウト）")
    show_pending_toasts()

    # Initialize deck and NPC strategy
    if "deck" not in st.session_state:
        st.session_state.deck = load_deck(CARD_IDS)
    if "npc_strategy" not in st.session_state:
        st.session_state.npc_strategy = RandomStrategy()

    # Initialize game state
    if "game_state" not in st.session_state:
        from shadow_bout.models import GameState, PlayerState

        st.session_state.game_state = GameState(
            player=PlayerState(), npc=PlayerState(), phase=Phase.START
        )

    game_state = st.session_state.game_state

    # Layout
    col1, col2 = st.columns([2, 1])

    with col1:
        if game_state.phase == Phase.START:
            st.write("NPCとの陰界戦戯を開始します！")
            if st.button(
                "シャドウバウト・エンゲージ", type="primary", use_container_width=True
            ):
                clear_reorder_widget_state()
                st.session_state.game_state = start_game(st.session_state.deck)
                st.session_state.selected_card_id = None
                st.rerun()

        elif game_state.phase in [
            Phase.SELECT,
            Phase.REVEAL,
            Phase.EFFECT_RESOLUTION,
            Phase.INTERACTIVE_EFFECT,
        ]:
            st.subheader(f"ラウンド {game_state.round_number} / 4")

            # NPC Side
            st.markdown("### 【NPC】")
            st.write(
                f"手札: {len(game_state.npc.hand)}枚 | 山札: {len(game_state.npc.deck)}枚"
            )
            st.write(
                f"勝ち札ポイント: {calculate_final_score(game_state.npc)}pt | あいこストック: {len(game_state.npc.draw_stock)}枚"
            )
            render_known_npc_hand(game_state)

            st.markdown("---")
            st.markdown("#### ── 場 ──")

            battle_cols = st.columns([5, 2, 5])
            with battle_cols[0]:
                st.markdown("**NPC**")
                if game_state.phase == Phase.SELECT:
                    st.info("[???] (セット済み)")
                else:
                    res = game_state.current_battle
                    base_pt = res.npc_card.base_point
                    final_pt = base_pt
                    if res.janken_result == JankenResult.DRAW:
                        if res.npc_point is not None:
                            final_pt = res.npc_point
                        else:
                            final_pt = calculate_effective_point(
                                res.npc_card, game_state.npc
                            )

                    pt_str = (
                        f"{base_pt} ➔ {final_pt}"
                        if final_pt != base_pt
                        else f"{base_pt}"
                    )

                    render_battle_card(
                        res.npc_card,
                        pt_str,
                        is_highlighted=res.janken_result == JankenResult.LOSE,
                    )

            with battle_cols[1]:
                st.markdown("&nbsp;")
                if game_state.phase != Phase.SELECT and game_state.current_battle:
                    render_janken_result()

            with battle_cols[2]:
                st.markdown("**あなた**")
                if game_state.phase == Phase.SELECT:
                    selected_card = find_card_by_id(
                        game_state.player.hand,
                        st.session_state.get("selected_card_id"),
                    )
                    if selected_card:
                        render_card_detail(selected_card)
                    else:
                        st.warning("[未選択]")
                else:
                    res = game_state.current_battle
                    base_pt = res.player_card.base_point
                    final_pt = base_pt
                    if res.janken_result == JankenResult.DRAW:
                        if res.player_point is not None:
                            final_pt = res.player_point
                        else:
                            final_pt = calculate_effective_point(
                                res.player_card, game_state.player
                            )

                    pt_str = (
                        f"{base_pt} ➔ {final_pt}"
                        if final_pt != base_pt
                        else f"{base_pt}"
                    )

                    render_battle_card(
                        res.player_card,
                        pt_str,
                        is_highlighted=res.janken_result == JankenResult.WIN,
                    )

            if game_state.phase == Phase.REVEAL:
                res = game_state.current_battle
                st.markdown("---")
                if res.outcome == RoundOutcome.WIN:
                    st.balloons()
                    st.header("🏆 あなたの勝ち！")
                elif res.outcome == RoundOutcome.LOSE:
                    st.header("💀 NPCの勝ち...")
                else:
                    st.header("🤝 引き分け！ (あいこストックへ)")

                if res.janken_result == JankenResult.DRAW:
                    st.write(
                        f"じゃんけんあいこ → ポイント比較: あなた {res.player_point} vs NPC {res.npc_point}"
                    )

                if st.button("次へ", type="primary", use_container_width=True):
                    st.session_state.game_state = proceed_to_next(game_state)
                    st.rerun()

            elif game_state.phase == Phase.INTERACTIVE_EFFECT:
                st.markdown("---")
                st.markdown("#### ── 効果の選択 ──")
                render_pending_effect_form(game_state)

            elif game_state.phase == Phase.EFFECT_RESOLUTION:
                render_effect_resolution_panel(game_state)

            elif game_state.phase == Phase.SELECT:
                st.markdown("---")
                st.markdown("#### ── あなたの手札 ──")
                hand = game_state.player.hand
                if not hand:
                    st.info("出せる手札がありません。")
                else:
                    selected_card_id = st.session_state.get("selected_card_id")
                    selected_card = find_card_by_id(hand, selected_card_id)
                    if selected_card_id and selected_card is None:
                        st.session_state.selected_card_id = None
                        selected_card_id = None

                    cols = st.columns(len(hand))
                    for i, card in enumerate(hand):
                        with cols[i]:
                            is_selected = card.id == selected_card_id
                            if render_selectable_card(
                                card,
                                is_selected=is_selected,
                                key=f"card_{i}",
                            ):
                                st.session_state.selected_card_id = card.id
                                st.rerun()

                    selected_card = find_card_by_id(
                        hand, st.session_state.get("selected_card_id")
                    )
                    st.markdown("---")
                    if selected_card:
                        st.caption(f"選択中: {render_card_info(selected_card)}")
                    else:
                        st.caption("カードを1枚選んでください。")

                    if st.button(
                        "エンゲージ",
                        type="primary",
                        disabled=selected_card is None,
                        use_container_width=True,
                    ):
                        st.session_state.game_state = select_card_stepwise(
                            game_state,
                            selected_card,
                            st.session_state.npc_strategy,
                        )
                        st.session_state.selected_card_id = None
                        st.rerun()

            # Player Stats
            st.markdown("---")
            st.markdown("### 【あなた】")
            st.write(
                f"手札: {len(game_state.player.hand)}枚 | 山札: {len(game_state.player.deck)}枚"
            )
            st.write(
                f"勝ち札ポイント: {calculate_final_score(game_state.player)}pt | あいこストック: {len(game_state.player.draw_stock)}枚"
            )

        elif game_state.phase == Phase.RESULT:
            st.header("🏁 最終結果")
            p_score = calculate_final_score(game_state.player)
            n_score = calculate_final_score(game_state.npc)

            res_col1, res_col2 = st.columns(2)
            res_col1.metric("あなたのスコア", f"{p_score} pt")
            res_col2.metric("NPCのスコア", f"{n_score} pt")

            if p_score > n_score:
                st.success("🎉 あなたの勝利です！")
            elif p_score < n_score:
                st.error("😭 NPCの勝利です...")
            else:
                st.warning("🤝 引き分けです！")

            if st.button("もう一度遊ぶ", use_container_width=True):
                clear_reorder_widget_state()
                st.session_state.game_state = start_game(st.session_state.deck)
                st.session_state.selected_card_id = None
                st.rerun()

    with col2:
        st.subheader("📜 バトルログ")
        for log in reversed(game_state.battle_log):
            st.write(log)

    render_footer_links()


if __name__ == "__main__":
    main()
