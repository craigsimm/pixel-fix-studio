from __future__ import annotations

from pixel_fix_3d.gui.persist import AppPreferences, app_preferences_to_dict, load_app_preferences


def test_load_app_preferences_uses_defaults_when_missing() -> None:
    assert load_app_preferences({}) == AppPreferences()


def test_load_app_preferences_merges_partial_data() -> None:
    preferences = load_app_preferences(
        {
            "preferences": {
                "show_floor_grid": False,
                "lighting_intensity": 1.25,
                "autorotate_speed": 0.75,
                "background_image_path": "C:/tmp/bg.png",
            }
        }
    )
    assert preferences == AppPreferences(
        show_floor_grid=False,
        show_face_highlight=True,
        lighting_intensity=1.25,
        autorotate_speed=0.75,
        background_enabled=False,
        background_image_path="C:/tmp/bg.png",
    )


def test_app_preferences_to_dict_round_trips() -> None:
    preferences = AppPreferences(
        show_floor_grid=False,
        show_face_highlight=False,
        lighting_intensity=1.25,
        autorotate_speed=1.25,
        background_enabled=True,
        background_image_path="C:/tmp/bg.png",
    )
    assert load_app_preferences({"preferences": app_preferences_to_dict(preferences)}) == preferences
