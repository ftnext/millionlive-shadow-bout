import streamlit as st

from shadow_bout import (
    Janken,
    JankenResult,
    Phase,
    RandomStrategy,
    RoundOutcome,
    calculate_final_score,
    load_deck,
    proceed_to_next,
    select_card,
    start_game,
)

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

st.set_page_config(page_title="Shadow Bout v0.1", layout="wide")


def render_card_info(card):
    return f"{card.name} {JANKEN_ICONS[card.janken]}{card.base_point}"


def main():
    st.title("🎴 シャドウバウト v0.1")

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
            st.write("NPCとのじゃんけんバトルを開始します！")
            if st.button("ゲーム開始", type="primary", use_container_width=True):
                st.session_state.game_state = start_game(st.session_state.deck)
                st.rerun()

        elif game_state.phase in [Phase.SELECT, Phase.REVEAL]:
            st.subheader(f"ラウンド {game_state.round_number} / 4")

            # NPC Side
            st.markdown("### 【NPC】")
            st.write(
                f"手札: {len(game_state.npc.hand)}枚 | 山札: {len(game_state.npc.deck)}枚"
            )
            st.write(
                f"勝ち札ポイント: {calculate_final_score(game_state.npc)}pt | あいこストック: {len(game_state.npc.draw_stock)}枚"
            )

            st.markdown("---")
            st.markdown("#### ── 場 ──")

            battle_cols = st.columns(2)
            with battle_cols[0]:
                st.markdown("**NPC**")
                if game_state.phase == Phase.SELECT:
                    st.info("[???] (セット済み)")
                else:
                    res = game_state.current_battle
                    st.success(render_card_info(res.npc_card))

            with battle_cols[1]:
                st.markdown("**あなた**")
                if game_state.phase == Phase.SELECT:
                    st.warning("[未選択]")
                else:
                    res = game_state.current_battle
                    st.success(render_card_info(res.player_card))

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

            elif game_state.phase == Phase.SELECT:
                st.markdown("---")
                st.markdown("#### ── あなたの手札 ──")
                hand = game_state.player.hand
                cols = st.columns(len(hand))
                for i, card in enumerate(hand):
                    with cols[i]:
                        if st.button(
                            render_card_info(card),
                            key=f"card_{i}",
                            use_container_width=True,
                        ):
                            st.session_state.game_state = select_card(
                                game_state, card, st.session_state.npc_strategy
                            )
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
                st.session_state.game_state = start_game(st.session_state.deck)
                st.rerun()

    with col2:
        st.subheader("📜 バトルログ")
        for log in reversed(game_state.battle_log):
            st.write(log)


if __name__ == "__main__":
    main()
