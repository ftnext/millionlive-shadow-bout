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
.venv/bin/python -m pytest
ruff format
ruff check --fix --extend-select I
```

Streamlit アプリを起動する場合:

```bash
.venv/bin/python -m streamlit run app.py
```

## GitHub (`gh`) 運用メモ（Codex Cloud）

Codex Cloud では `gh` をセットアップ済み。Issue確認、ブランチpush、PR作成まで `gh` で実行する。

まず認証状態を確認:

```bash
gh auth status -h github.com
```

`git push` が認証エラーになる場合は、`gh` の認証を git に反映:

```bash
gh auth setup-git
```

Issue確認:

```bash
gh issue view https://github.com/ftnext/millionlive-shadow-bout/issues/<number>
```

ブランチpush:

```bash
git push -u origin <branch>
```

PR作成（本文のクオート崩れを避けるため `--body-file` 推奨）:

```bash
cat > /tmp/pr_body.md <<'EOF'
## 概要
- ...

## テスト
- ...
EOF

gh pr create \
  -R ftnext/millionlive-shadow-bout \
  --base main \
  --head <branch> \
  --title "feat(...): ..." \
  --body-file /tmp/pr_body.md
```
