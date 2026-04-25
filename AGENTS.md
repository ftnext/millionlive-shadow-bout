# AGENTS.md

## プロジェクト概要

「陰界戦戯（シャドウバウト）」を NPC 相手に遊べる Python + Streamlit アプリです。

- `app.py`: Streamlit UI
- `shadow_bout/`: ゲームルール、状態遷移、カード効果、NPC 戦略
- `cards.jsonl`: カードデータ
- `docs/`: ルールと実装計画
- `tests/`: ドメインロジックの pytest

ゲームロジックは Streamlit に依存させず、`shadow_bout` パッケージ内で完結させます。UI は `GameState` を表示し、ユーザー入力をドメイン関数へ渡す薄い層にします。

## 作業ルール

- ユーザーへの返答、プラン、説明、成果物は日本語で書いてください。
- 既存の設計方針とファイル構成を優先し、不要な大きなリファクタリングは避けてください。
- 実装後はテストと lint/format を確認してください。
- コミットメッセージは Conventional Commits に従ってください。

## コマンド

`ruff` は `uv tool install ruff` 済みのため、直接実行します。

```bash
uv run pytest
ruff format
ruff check --fix --extend-select I
```

Streamlit アプリを起動する場合:

```bash
uv run streamlit run app.py
```
