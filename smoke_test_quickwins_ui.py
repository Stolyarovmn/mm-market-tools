#!/usr/bin/env python3
from pathlib import Path


HTML = Path(__file__).with_name("docs").joinpath("index.html").read_text(encoding="utf-8")


def assert_contains(needle: str) -> None:
    assert needle in HTML, f"missing UI artifact: {needle}"


def main() -> None:
    assert_contains('data-tab="quickwins"')
    assert_contains("function renderQuickWins()")
    assert_contains("PENDING_QUICKWINS_KEY")
    assert_contains("function markQuickWinChanged(")
    assert_contains("function quickWinState(")
    assert_contains("Ожидает перепроверки")
    assert_contains("Отметить как изменено")
    assert_contains("Обновить данные и перепроверить")
    assert_contains("Подтвердилось после обновления")
    assert_contains("Первым делом:")
    print("SMOKE_QUICKWINS_UI_OK")


if __name__ == "__main__":
    main()
