from pixel_fix_studio.content import LAUNCHER_CARDS, SIDEBAR_PRIMARY_ITEMS, SIDEBAR_SECONDARY_ITEMS


def test_launcher_cards_exist() -> None:
    assert len(LAUNCHER_CARDS) == 2
    assert {card.key for card in LAUNCHER_CARDS} == {"pixel_fix_2d", "pixel_fix_3d"}


def test_sidebar_sections_exist() -> None:
    assert [item.key for item in SIDEBAR_PRIMARY_ITEMS] == ["projects", "palettes", "textures"]
    assert [item.key for item in SIDEBAR_SECONDARY_ITEMS] == ["settings", "docs"]
