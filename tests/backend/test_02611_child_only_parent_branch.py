from app.structure_view import render_structure


def test_02611_child_only_event_omits_empty_parent_triplet_without_day_folders():
    text = "\n".join(render_structure(
        "2026",
        "07-19 - Test Archiv",
        [],
        [
            {"folder_name": "07-19 00-00 - 07-20 23-59 - Teil A", "day_keys": ["2026-07-19", "2026-07-20"]},
            {"folder_name": "07-21 00-00 - 07-21 23-59 - Teil B", "day_keys": ["2026-07-21"]},
        ],
        False,
    ))
    before_child = text.split("Teil A", 1)[0]
    assert "Alle" not in before_child
    assert "Sortiert" not in before_child
    assert "Export" not in before_child
    assert text.count("Alle") == 2
    assert text.count("Sortiert") == 2
    assert text.count("Export") == 2


def test_02611_child_only_event_omits_empty_parent_days_with_day_folders():
    text = "\n".join(render_structure(
        "2026",
        "07-19 - Test Archiv",
        [],
        [
            {"folder_name": "Teil A", "day_keys": ["2026-07-19", "2026-07-20"]},
            {"folder_name": "Teil B", "day_keys": ["2026-07-21"]},
        ],
        True,
    ))
    prefix = text.split("Teil A", 1)[0]
    assert "Alle" not in prefix
    assert "2026-07-19" not in prefix
    assert "2026-07-19" in text
    assert "2026-07-21" in text


def test_02611_parent_triplet_remains_when_parent_has_own_files():
    text = "\n".join(render_structure(
        "2026",
        "07-19 - Test Archiv",
        ["2026-07-20"],
        [{"folder_name": "Teil A", "day_keys": ["2026-07-19"]}],
        False,
    ))
    prefix = text.split("Teil A", 1)[0]
    assert "Alle" in prefix
    assert "Sortiert" in prefix
    assert "Export" in prefix


def test_02611_event_without_children_keeps_normal_parent_triplet():
    text = "\n".join(render_structure(
        "2026",
        "07-19 - Test",
        [],
        [],
        False,
    ))
    assert "Alle" in text
    assert "Sortiert" in text
    assert "Export" in text
