"""RC2 first-library configuration: no duplicate storage, durable settings, isolation."""
from fastapi.testclient import TestClient

from app import main
from app.database import database_connection
from app.event_layout import get_global_default
from app.legacy_adoption_mode import initial_preferences_required
from app.library_context import resolve_library_context
from app.library_registry import get_library
from tests.backend.test_legacy_adoption_integration import fresh_main, _json, _onboard


def test_new_library_must_set_preferences_before_adoption_choice(fresh_main):
    _, _, registry, _ = fresh_main
    client = _onboard(fresh_main, confirm_preferences=False)
    assert initial_preferences_required(registry)
    for path in ("/", "/workspace", "/transfer", "/setup/adoption"):
        response = client.get(path)
        assert response.status_code == 303
        assert response.headers["location"] == "/setup/preferences"
    response = client.get("/setup/preferences")
    assert response.status_code == 200
    assert "Synthetic Main" in response.text
    assert "folder-tree" in response.text
    assert 'id="first-library-next"' in response.text
    assert _json(client, "POST", "/api/setup/adoption", status=409,
                 json={"decision": "adopting"})["code"] == "initial_setup_required"
    assert _json(client, "GET", "/api/jobs", status=409)["code"] == "initial_setup_required"
    assert _json(client, "GET", "/api/settings/event-naming")["library_id"] == "main"
    assert "layout" in _json(client, "GET", "/api/settings/event-folder-layout")
    assert _json(client, "POST", "/api/setup/preferences/continue") == {
        "next": "/setup/adoption"
    }
    assert not initial_preferences_required(registry)
    assert client.get("/").headers["location"] == "/setup/adoption"
    assert client.get("/setup/preferences").headers["location"] == "/setup/adoption"
    assert _json(client, "GET", "/api/settings/event-naming", status=409)[
        "code"
    ] == "initial_setup_required"


def test_library_specific_preferences_survive_restart_skip_and_second_library(fresh_main):
    _, database, registry, archive = fresh_main
    client = _onboard(fresh_main, confirm_preferences=False)
    naming = _json(client, "GET", "/api/settings/event-naming")
    naming.pop("library_id")
    naming.update({
        "no_event_label": "Meine Sammlung", "include_year": True,
        "subevent_include_time": True,
    })
    saved = _json(client, "PUT", "/api/settings/event-naming", json=naming)
    assert saved["no_event_label"] == "Meine Sammlung"
    layout = _json(client, "GET", "/api/settings/event-folder-layout")
    modified = {
        "structure_enabled": True,
        "input_path": "Originale",
        "layout": {"version": 2, "nodes": [
            {"id": "rc2-originals", "name": "Originale", "children": []},
            {"id": "rc2-export", "name": "Bearbeitet", "role": "export", "children": []},
        ]},
    }
    layout = _json(client, "PUT", "/api/settings/event-folder-layout", json=modified)
    with database_connection(database) as connection:
        assert get_global_default(connection) == layout
    assert get_library(registry, "main")["settings"]["event_naming"]["no_event_label"] == "Meine Sammlung"
    main.startup_database()
    restarted = TestClient(main.app, follow_redirects=False)
    assert restarted.get("/").headers["location"] == "/setup/preferences"
    assert _json(restarted, "GET", "/api/settings/event-naming")["no_event_label"] == "Meine Sammlung"
    assert _json(restarted, "GET", "/api/settings/event-folder-layout") == layout
    _json(restarted, "POST", "/api/setup/preferences/continue")
    _json(restarted, "POST", "/api/setup/adoption", json={"decision": "skipped"})
    assert restarted.get("/").status_code == 200
    assert _json(restarted, "GET", "/api/settings/event-naming")["include_year"] is True
    assert _json(restarted, "GET", "/api/settings/event-folder-layout") == layout
    assert _json(restarted, "POST", "/api/setup/preferences/continue", status=409)[
        "code"
    ] == "legacy_adoption_inactive"

    other_archive = archive.with_name("another-library-archive")
    other_archive.mkdir()
    other = _json(restarted, "POST", "/api/libraries", status=201,
                  json={"display_name": "Second Library", "archive_root": str(other_archive)})["library"]
    other_id = other["library_id"]
    assert other_id != "main"
    other_naming = _json(restarted, "GET", "/api/settings/event-naming", library=other_id)
    other_layout = _json(restarted, "GET", "/api/settings/event-folder-layout", library=other_id)
    assert other_naming["library_id"] == other_id
    assert other_naming["no_event_label"] != "Meine Sammlung"
    assert other_layout != layout
    assert _json(restarted, "GET", "/api/settings/event-naming", library="main")[
        "no_event_label"
    ] == "Meine Sammlung"


def test_library_preferences_persist_after_selecting_adoption(fresh_main):
    _, database, registry, _ = fresh_main
    client = _onboard(fresh_main, confirm_preferences=False)
    naming = _json(client, "GET", "/api/settings/event-naming")
    naming.pop("library_id")
    naming["no_event_label"] = "Bestandsfotos"
    _json(client, "PUT", "/api/settings/event-naming", json=naming)
    layout = _json(client, "GET", "/api/settings/event-folder-layout")
    assert _json(client, "POST", "/api/setup/preferences/continue")["next"] == "/setup/adoption"
    assert _json(client, "POST", "/api/setup/adoption",
                 json={"decision": "adopting"}) == {"next": "/legacy-adoption"}
    assert get_library(registry, "main")["settings"]["event_naming"]["no_event_label"] == "Bestandsfotos"
    with database_connection(database) as connection:
        assert get_global_default(connection) == layout


def test_preferences_are_rejected_when_invalid(fresh_main):
    client = _onboard(fresh_main, confirm_preferences=False)
    naming = _json(client, "GET", "/api/settings/event-naming")
    naming.pop("library_id")
    naming["no_event_label"] = "../escape"
    assert _json(client, "PUT", "/api/settings/event-naming", status=422,
                 json=naming)["detail"]
    layout = _json(client, "GET", "/api/settings/event-folder-layout")
    layout["input_path"] = "../../invalid"
    assert _json(client, "PUT", "/api/settings/event-folder-layout", status=422,
                 json=layout)["detail"]
