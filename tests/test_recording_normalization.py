from robot_automation_studio.models import Scenario, Step


def test_normalize_recorded_hierarchy_paths_creates_variables_and_rewrites_steps() -> None:
    from robot_automation_studio.recording_normalization import (
        normalize_recorded_hierarchy_paths_to_variables,
    )

    scenario = Scenario(
        name="Normalization",
        target_window_hint="Unity",
        variables=[],
        steps=[
            Step(
                action="click",
                title="Select tail",
                params={
                    "hierarchy_path": "AvatarRoot/Hair/Tail",
                    "target": {
                        "strategy": "unity_hierarchy",
                        "unity_hierarchy": {"path": "AvatarRoot/Hair/Tail", "match_mode": "exact"},
                        "fallbacks": [
                            {
                                "strategy": "unity_hierarchy",
                                "unity_hierarchy": {"path": "*/Hair/Tail", "match_mode": "exact"},
                            }
                        ],
                    },
                },
            ),
            Step(
                action="click",
                title="Select hips",
                params={
                    "hierarchy_path": "AvatarRoot/Armature/Hips",
                    "target": {
                        "strategy": "unity_hierarchy",
                        "unity_hierarchy": {
                            "path": "AvatarRoot/Armature/Hips",
                            "match_mode": "exact",
                        },
                        "fallbacks": [
                            {
                                "strategy": "unity_hierarchy",
                                "unity_hierarchy": {
                                    "path": "*/Armature/Hips",
                                    "match_mode": "exact",
                                },
                            }
                        ],
                    },
                },
            ),
        ],
    )

    normalize_recorded_hierarchy_paths_to_variables(scenario, step_start_index=0)

    variables_by_id = {
        str(item.get("id")): item for item in scenario.variables if isinstance(item, dict)
    }
    assert variables_by_id["avatar_root"]["default"] == "AvatarRoot"
    assert variables_by_id["hier_hair_tail"]["default"] == "Hair/Tail"
    assert variables_by_id["hier_armature_hips"]["default"] == "Armature/Hips"

    step0 = scenario.steps[0].to_dict()
    assert step0["target"]["unity_hierarchy"]["path"] == "${avatar_root}/${hier_hair_tail}"
    assert step0["target"]["fallbacks"][0]["unity_hierarchy"]["path"] == "*/${hier_hair_tail}"

    step1 = scenario.steps[1].to_dict()
    assert step1["target"]["unity_hierarchy"]["path"] == "${avatar_root}/${hier_armature_hips}"
    assert step1["target"]["fallbacks"][0]["unity_hierarchy"]["path"] == "*/${hier_armature_hips}"


def test_normalize_recorded_hierarchy_paths_is_idempotent() -> None:
    from robot_automation_studio.recording_normalization import (
        normalize_recorded_hierarchy_paths_to_variables,
    )

    scenario = Scenario(
        name="Normalization",
        target_window_hint="Unity",
        variables=[],
        steps=[
            Step(
                action="click",
                title="Select tail",
                params={
                    "target": {
                        "strategy": "unity_hierarchy",
                        "unity_hierarchy": {"path": "AvatarRoot/Hair/Tail", "match_mode": "exact"},
                        "fallbacks": [
                            {
                                "strategy": "unity_hierarchy",
                                "unity_hierarchy": {"path": "*/Hair/Tail", "match_mode": "exact"},
                            }
                        ],
                    },
                },
            )
        ],
    )

    normalize_recorded_hierarchy_paths_to_variables(scenario, step_start_index=0)
    normalize_recorded_hierarchy_paths_to_variables(scenario, step_start_index=0)

    variable_ids = [str(item.get("id")) for item in scenario.variables if isinstance(item, dict)]
    assert variable_ids.count("avatar_root") == 1
    assert variable_ids.count("hier_hair_tail") == 1
