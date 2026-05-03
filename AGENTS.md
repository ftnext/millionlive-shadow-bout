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
- 実装・修正・機能追加を求められた場合は、GitHub Issue の URL が指定されていなくても、下記「実装依頼の完了条件」に従ってください。
- レビュー依頼、調査依頼、質問への回答のみの依頼では、ユーザーが明示しない限りコミット・push・PR作成は行いません。

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

## GitHub (`gh`) 利用前提

Codex Cloud では `gh` をセットアップ済み。Issue確認、ブランチpush、PR作成まで `gh` / `git` で実行する。
作業ブランチ名は常に `work` とせず、依頼内容にもとづく短い英語の名前にする（例: `fix-npc-action-log`, `feat-card-filter`）。

まず認証状態を確認:

```bash
gh auth status -h github.com
```

`git push` が認証エラーになる場合は、`gh` の認証を git に反映:

```bash
gh auth setup-git
```

### 実装依頼の完了条件（必須）

- 実装・修正・機能追加を求められた場合は、ユーザーが「PRを作って」と明示していなくても、ブランチ作成からPR作成までを一連の作業として完了させる。
- GitHub Issue の URL が指定されている場合は、実装前に `gh issue view <issue-url>` で内容を確認する。
- 原則として以下をこの順番で実施する:
  1. 依頼内容にもとづく短い英語名の作業ブランチを作る
  2. 実装する
  3. テストと lint/format を実行する
  4. Conventional Commits に従ってコミットする
  5. `git push -u origin <branch>` でブランチを push する（初回のみ `-u`）
  6. `gh pr create -R ftnext/millionlive-shadow-bout --base main --head <branch> --title "<conventional commit準拠>" --body-file <file>` で PR を作成する
- 既存PRが同一ブランチにある場合は新規作成せず、追加コミットをpushしたうえで既存PRを更新対象とする。
- 変更がない（コミットしない）場合は PR を作成しない。
- PR本文はクオート崩れを避けるため、原則として `--body-file` を使う。

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
