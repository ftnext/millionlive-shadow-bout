# 開発用シナリオモード

じゃんけんで勝負がつくケースが多く、効果（あいこ時のポイント比較や `effect` 発動）の検証が手作業だと再現しづらい。
このシナリオモードは、ローカル開発時のみ動作し、**初期手札・各ラウンドの出し手・WILDCARD 宣言**を任意の粒度で部分指定できる仕組みです。

## 有効化条件

シナリオモードのUIは以下の両方を満たすときだけ表示されます。

1. 環境変数 `SHADOW_BOUT_DEV=1` を設定して Streamlit アプリを起動
2. プロジェクトルートに `dev_scenario.json` を配置

```bash
SHADOW_BOUT_DEV=1 .venv/bin/python -m streamlit run app.py
```

## デプロイ環境では使えない仕様

- Streamlit Cloud 等のデプロイ先で `SHADOW_BOUT_DEV` を設定しない限り、シナリオUIは描画されません。
- `dev_scenario.json` は `.gitignore` 対象です。リポジトリ経由でデプロイ環境に持ち込まれることはありません。

> 注意: 「絶対に検出して無効化する」のではなく、**「Cloud で env var を設定しない」**運用前提です。

## シナリオファイルの形式

`dev_scenario.json`（プロジェクトルート、JSON）。すべてのフィールドが optional です。

```json
{
  "player_hand": ["card_14"],
  "npc_hand": ["card_38", "card_25"],
  "rounds": [
    {"player_card": "card_14"},
    null,
    {"npc_card": "card_38", "npc_wildcard": "rock"},
    {"player_card": "card_11", "player_wildcard": "scissors"}
  ]
}
```

### `player_hand` / `npc_hand`

- 0〜5 件のカード ID。
- ID は `app.py` の `CARD_IDS`（固定13枚プール）に含まれている必要があります。
- 重複不可。
- 指定したカードは初期手札（5枚）に必ず含まれます。残りの枠と山札はシャッフル順で埋められます。

### `rounds`

- 0〜4 件のリスト。先頭要素がラウンド 1、2 番目がラウンド 2、…と対応します。
- 関心のないラウンドは `null` を入れてください（指定無し扱い）。
- 末尾以降の関心無しラウンドはリストから省略してかまいません（例: ラウンド 1 のみ指定なら `[{"player_card": "card_14"}]`）。
- **空オブジェクト `{}` は不可**。各ラウンドは以下のうち最低 1 つを指定してください。
  - `player_card`: そのラウンドでプレイヤーが選択するカード ID
  - `npc_card`: そのラウンドで NPC が選択するカード ID
  - `player_wildcard`: プレイヤーの WILDCARD カードを `"rock" | "scissors" | "paper"` のどれとして扱うか
  - `npc_wildcard`: NPC 同上

## 動作仕様

- 「シナリオでエンゲージ（開発用）」ボタンを押すと、`CARD_IDS` をベースに required hand を満たして配布します。
- 各ラウンドの SELECT フェーズに入ると、`player_card` / `player_wildcard` が指定されていれば自動的に「選択済み状態」にプリセレクトされます。エンゲージは開発者が手で押してください。
- NPC は `ScriptedStrategy` で動作し、`npc_card` / `npc_wildcard` の指定がある面だけシナリオ通りに、未指定の面は通常通りランダムに動作します。
- カード効果の選択 UI（あいこ時の効果解決など）は通常通り手動で操作します。これがシナリオモードの主な検証対象です。
- 「もう一度遊ぶ」を押すと、同じシナリオで再度配布します（シャッフル結果は変わるが required hand は満たす）。

## トラブルシュート

- ボタンが表示されない: `SHADOW_BOUT_DEV=1` を設定してアプリを再起動したか確認してください。
- ボタンが非活性: `dev_scenario.json` がプロジェクトルートに存在するか確認してください。
- エンゲージ時にエラー: JSON の形式・カード ID の妥当性を確認してください。エラーメッセージが画面上に表示されます。
