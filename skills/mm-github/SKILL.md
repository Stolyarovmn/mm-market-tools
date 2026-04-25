# Skill: mm-github

Единый GitHub-интерфейс для проекта mm-market-tools.
Работает одинаково для Claude (Cowork/Bash) и Codex (CLI).

## Быстрый старт

```bash
export GH_TOKEN="ghp_..."          # GitHub PAT (repo + workflow scopes)
export GH_REPO="username/mm-market-tools"
export AGENT_NAME="claude"         # или "codex"

python3 skills/mm-github/mm_github.py status
```

## Команды

| Команда | Что делает |
|---------|-----------|
| `status` | Состояние репо, CI, Pages URL, задачи, локи |
| `setup` | Первый запуск: создать GitHub-репо, push, включить Pages |
| `push [--message "..."]` | Commit all + git push |
| `deploy-dashboard` | Скопировать dashboard HTML → docs/index.html → push → GitHub Pages |
| `sync-tasks` | TASKS.md → GitHub Issues (создаёт недостающие) |
| `update-wiki` | docs/*.md + README/ROADMAP → GitHub Wiki |
| `new-release [--version v0.5]` | Тег + Release на текущем коммите |
| `lock --file path/to/file` | Занять файл (защита от конфликтов агентов) |
| `unlock --file path/to/file` | Освободить файл |
| `check-locks` | Показать все активные локи |

## Протокол совместной работы агентов

```
Перед редактированием shared файла:
  python3 skills/mm-github/mm_github.py lock --file core/daily_action_plan.py

После окончания работы:
  python3 skills/mm-github/mm_github.py unlock --file core/daily_action_plan.py
  python3 skills/mm-github/mm_github.py push --message "feat: улучшение scoring"
```

**Правило**: кто занял лок первым — тот работает. Второй агент ждёт или берёт другой файл.
Локи хранятся в `.locks/` (gitignored), видны обоим агентам через shared filesystem.

## Переменные окружения

```bash
GH_TOKEN    # GitHub Personal Access Token
            # Scopes: repo, workflow
            # Создать: github.com/settings/tokens → Generate new token (classic)

GH_REPO     # owner/repo-name
            # Пример: "wonders-shop/mm-market-tools"

AGENT_NAME  # "claude" | "codex" | "gemini"
            # Используется в commit messages и lock attribution
```

## GitHub Pages

После `setup` и первого `deploy-dashboard`:
- URL: `https://{owner}.github.io/mm-market-tools/`
- Источник: ветка `main`, папка `/docs`
- Обновление: автоматически при каждом `push` (30-60 сек)

Команда `deploy-dashboard` берёт последний `magnit_command_center_*.html`
из рабочей директории, кладёт его в `docs/index.html` и делает push.

## GitHub Actions (auto-deploy)

После setup создаётся `.github/workflows/deploy-pages.yml`:
- Триггер: push в main
- Действие: публикует `docs/` на GitHub Pages

Для scheduled refresh добавить `.github/workflows/daily-plan.yml`:
```yaml
on:
  schedule:
    - cron: '0 6 * * *'  # 06:00 UTC = 09:00 MSK
```

## Совместимость

- Claude Cowork: запускает через `Bash` tool
- Codex: запускает напрямую в терминале
- Требует Python 3.10+, git, gh CLI
- gh CLI path: `/sessions/keen-wizardly-turing/gh_bin` (Cowork) или `/usr/local/bin/gh` (WSL)
