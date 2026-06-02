from pathlib import Path

from app.live2d_action_presets import (
    ACTION_SHOWCASE_SIZE,
    LIVE2D_ACTION_PARAMETER_RANGES,
    compact_actions_for_showcase,
    compact_action_for_manifest,
    action_showcase_path,
    load_live2d_action_showcase_ids,
    filter_live2d_action_presets,
    load_live2d_action_preset_catalog,
    normalize_action_parameters,
    save_live2d_action_showcase_ids,
)


ROOT = Path(__file__).resolve().parents[1]


def test_live2d_action_catalog_has_200_balanced_presets():
    catalog = load_live2d_action_preset_catalog(ROOT)
    actions = catalog["actions"]

    assert catalog["format"] == "pet_buddy_live2d_action_preset_catalog_v1"
    assert len(actions) == 200
    assert len({action["id"] for action in actions}) == 200

    categories = {}
    for action in actions:
        categories[action["category"]] = categories.get(action["category"], 0) + 1
    assert set(categories.values()) == {25}
    assert len(categories) == 8


def test_live2d_action_parameters_stay_within_rig_ranges():
    catalog = load_live2d_action_preset_catalog(ROOT)

    for action in catalog["actions"]:
        params = normalize_action_parameters(action["parameters"])
        assert params
        for key, value in params.items():
            low, high = LIVE2D_ACTION_PARAMETER_RANGES[key]
            assert low <= value <= high


def test_live2d_action_filter_and_manifest_compaction():
    catalog = load_live2d_action_preset_catalog(ROOT)
    actions = catalog["actions"]

    raised = filter_live2d_action_presets(actions, category="arms_raised_or_overhead")
    core_only = filter_live2d_action_presets(actions, include_alternate_art=False)
    query = filter_live2d_action_presets(actions, query="比心")

    assert len(raised) == 25
    assert all(not action.get("requires_alternate_art") for action in core_only)
    assert any("比心" in action["label"] for action in query)

    compact = compact_action_for_manifest(query[0])
    assert "source_basis" not in compact
    assert compact["parameters"]
    assert set(compact["parameters"]).issubset(LIVE2D_ACTION_PARAMETER_RANGES)


def test_live2d_action_showcase_allows_empty_slots(tmp_path: Path):
    source_catalog = ROOT / "assets" / "live2d_modeling" / "pose_study" / "live2d_action_presets.json"
    target_catalog = tmp_path / "assets" / "live2d_modeling" / "pose_study" / "live2d_action_presets.json"
    target_catalog.parent.mkdir(parents=True)
    target_catalog.write_text(source_catalog.read_text(encoding="utf-8"), encoding="utf-8")

    catalog = load_live2d_action_preset_catalog(tmp_path)
    wanted = [
        catalog["actions"][20]["id"],
        "",
        "missing-action",
        catalog["actions"][5]["id"],
        catalog["actions"][20]["id"],
        "",
    ]
    saved = save_live2d_action_showcase_ids(tmp_path, wanted, owner_id="我的Live2D男性模型")
    loaded = load_live2d_action_showcase_ids(tmp_path, owner_id="我的Live2D男性模型")
    compact = compact_actions_for_showcase(catalog["actions"], loaded)

    assert len(saved) == len(wanted)
    assert loaded == saved
    assert saved[0] == catalog["actions"][20]["id"]
    assert saved[1] == ""
    assert saved[2] == ""
    assert saved[3] == catalog["actions"][5]["id"]
    assert saved[4] == ""
    assert saved[5] == ""
    assert "missing-action" not in saved
    assert len(compact) == 2
    assert len(saved) < ACTION_SHOWCASE_SIZE
    assert action_showcase_path(tmp_path, "我的Live2D男性模型").is_file()
    assert not action_showcase_path(tmp_path, "另一个自建角色").exists()
