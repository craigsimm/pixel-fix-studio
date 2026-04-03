from pixel_fix.gui.state import PreviewSettings, SettingsSession, UNDO_HISTORY_LIMIT


def test_apply_tracks_undo_history() -> None:
    session = SettingsSession()
    session.apply(generated_shades=8)
    assert session.current.generated_shades == 8
    assert session.history.can_undo()


def test_undo_restores_previous_settings() -> None:
    session = SettingsSession(PreviewSettings(generated_shades=4, pixel_width=2))
    session.apply(generated_shades=8)
    session.apply(pixel_width=4)

    restored = session.undo()
    assert restored.generated_shades == 8
    assert restored.pixel_width == 2

    restored = session.undo()
    assert restored.generated_shades == 4
    assert restored.pixel_width == 2


def test_redo_restores_next_settings() -> None:
    session = SettingsSession(PreviewSettings(generated_shades=4, pixel_width=2))
    session.apply(generated_shades=8)
    session.apply(pixel_width=4)

    session.undo()
    restored = session.redo()

    assert restored.generated_shades == 8
    assert restored.pixel_width == 4


def test_settings_history_is_bounded() -> None:
    session = SettingsSession()

    for value in range(UNDO_HISTORY_LIMIT + 5):
        session.apply(pixel_width=(value % 8) + 1, generated_shades=(2, 4, 6, 8, 10)[value % 5])

    undo_count = 0
    while session.history.can_undo():
        session.undo()
        undo_count += 1

    assert undo_count == UNDO_HISTORY_LIMIT
