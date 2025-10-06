#!/usr/bin/env python3
# /tools/new_project.py
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    ".gitignore": """
# Python
__pycache__/
*.pyc
.venv/
# Node
node_modules/
# OS
.DS_Store
# IDE
.idea/
.vscode/
""".strip(),
    ".editorconfig": """
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 2
trim_trailing_whitespace = true
""".strip(),
    ".pre-commit-config.yaml": """
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-yaml
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black
        language_version: python3
  - repo: https://github.com/igorshubovych/markdownlint-cli
    rev: v0.39.0
    hooks:
      - id: markdownlint
        args: ["-q"]
""".strip(),
    "README.md": """
# Аналитический Дашборд (MVP) + Автоматизация VK Ads

Репозиторий артефактов проекта: документы, схемы, каркасы кода (Apps Script и Python-сервис VK Ads).

## Разделы
- `docs/` — документация
- `schemas/` — схемы данных (Sheets)
- `appscript/` — код Google Apps Script (A2)
- `vk-python/` — Python-сервис (B0–B3)
- `ops/` — чек-листы и операционные шаблоны
- `tools/` — служебные скрипты
""".strip(),
    "CHANGELOG.md": """
# Changelog

## [0.1.0] - 2025-09-30
- Инициализация репозитория и базовых шаблонов.
""".strip(),
    "LICENSE": "MIT License\n",
    "docs/PROJECT_OVERVIEW.md": """
# Обзор проекта
Цель: быстрый MVP дашборда в DataLens + полуавтомат VK + полная автоматизация VK отдельным сервисом.
Ограничения: бюджет 45 000 ₽, сроки 10–14 дней, без платных коннекторов.
""".strip(),
    "docs/SCOPE_AND_CONTRACT.md": """
# Объём работ и условия
- MVP (5–7 дней): DataLens + Sheets + Apps Script (QTickets)
- VK Python (+5–7 дней): отдельный сервис
Оплата 50/50: 22 500 ₽ аванс, 22 500 ₽ после Акта.
""".strip(),
    "docs/COMMUNICATION_PLAN.md": """
# План коммуникаций
- Ежедневный короткий апдейт в чат: статус/риски/план на день
- Еженедельное демо (30 мин)
- Каналы: e-mail, мессенджер (по согласованию)
SLA ответов: рабочие часы MSK, критические ≤ 4ч
""".strip(),
    "docs/RISK_LOG.md": """
# Журнал рисков
| ID | Риск                          | Вероятн. | Влияние | План реакции               |
|----|-------------------------------|----------|---------|----------------------------|
| R1 | Задержка стартовых доступов   | Сред     | Сред    | Буфер 1–2 дня, эскалация   |
| R2 | Меняется формат CSV QTickets  | Низк     | Сред    | try/catch, быстрый хотфикс |
""".strip(),
    "docs/DOD_CHECKLIST_A0.md": """
# DoD — EPIC A0
- [ ] Репозиторий создан по структуре
- [ ] Pre-commit установлен и активирован
- [ ] COMMUNICATION_PLAN и RISK_LOG заполнены (черновик)
- [ ] Ссылка на борд задач добавлена в PROJECT_OVERVIEW
""".strip(),
    "docs/DOR_CHECKLIST_A0.md": """
# DoR — EPIC A0
- [ ] Подтверждены сроки и оплата 50/50
- [ ] Назначены ответственные и каналы связи
- [ ] Утверждён список эпиков A0–B3
""".strip(),
    "docs/TEMPLATES/ISSUE_TEMPLATE.md": """
# Шаблон задачи
**Название:**
**Эпик:**
**Описание:**
**Критерии приёмки:**
**Связанные документы/ссылки:**
""".strip(),
    "docs/TEMPLATES/MEETING_NOTES_TEMPLATE.md": """
# Шаблон заметок встречи
**Дата/время:**
**Участники:**
**Повестка:**
**Итоги/решения:**
**Действия и ответственные:**
""".strip(),
    "ops/CHECKLIST_KICKOFF.md": """
# Кик-офф чек-лист
- [ ] Представились, подтвердили роли
- [ ] Подтвердили цели и ограничения
- [ ] Договорились о каналах и времени синков
- [ ] Зафиксировали список доступов и дедлайны их выдачи
""".strip(),
    "ops/EMAIL_TEMPLATES.md": """
# Шаблоны писем

## 1) Запрос на данные/доступы (черновик)
Здравствуйте! Для старта работ по дашборду прошу предоставить доступы по списку (во вложении) и подтвердить часовой пояс отчётности. Спасибо!
""".strip(),
}

DIRS = [
    "docs/TEMPLATES",
    "schemas/sheets",
    "appscript",
    "vk-python",
    "ops",
    "tools",
]

def ensure_dirs():
    for d in DIRS:
        (ROOT / d).mkdir(parents=True, exist_ok=True)

def write_files():
    for rel, content in FILES.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content + "\n", encoding="utf-8")
            print("created:", rel)
        else:
            print("skip (exists):", rel)

if __name__ == "__main__":
    ensure_dirs()
    write_files()
    print("Project skeleton ready.")