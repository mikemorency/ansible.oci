from __future__ import absolute_import, division, print_function
__metaclass__ = type

import types

import pytest

from .conftest import (
    DummyModule,
    ExitJsonCalled,
    FailJsonCalled,
    FakeModel,
    FakeResponse,
    install_fake_oci as shared_install_fake_oci,
    load_collection_module,
    make_module_instance,
    raising,
)


REPOSITORY_MODEL_NAMES = (
    "CreateRepositoryDetails",
    "UpdateRepositoryDetails",
    "MirrorRepositoryConfig",
    "TriggerSchedule",
)


def install_fake_oci(monkeypatch):
    """Install fake OCI modules including the DevOps namespace.

    Args:
        monkeypatch: Pytest fixture for replacing OCI modules.

    Returns:
        The fake oci module and ServiceError class.
    """
    oci_module, service_error = shared_install_fake_oci(monkeypatch)
    oci_module.devops = types.SimpleNamespace(
        DevopsClient=type("FakeDevopsClient", (), {}),
        models=types.SimpleNamespace(
            **{model_name: FakeModel for model_name in REPOSITORY_MODEL_NAMES}
        ),
    )
    return oci_module, service_error


def load_repository_module(monkeypatch):
    """Load the DevOps repository module with fake OCI types.

    Args:
        monkeypatch: Pytest fixture for replacing OCI modules.

    Returns:
        The loaded repository module.
    """
    install_fake_oci(monkeypatch)
    return load_collection_module("oci_devops_repository")


def make_repository(module_obj, params, client=None, check_mode=False):
    """Create a repository module instance without OCI credentials.

    Args:
        module_obj: The loaded repository module.
        params: The parameters for the module instance.
        client: An optional fake client.
        check_mode: Whether Ansible check mode is enabled.

    Returns:
        The repository module instance.
    """
    return make_module_instance(
        module_obj,
        "OciDevopsRepositoryModule",
        params,
        client=client,
        check_mode=check_mode,
    )


def passthrough_retry(monkeypatch, instance):
    """Make call_with_retry call the method directly."""
    monkeypatch.setattr(
        instance, "call_with_retry", lambda method, **kwargs: method(**kwargs)
    )


def test_main_argument_contract(monkeypatch):
    """Expose the repository options and run the module with check mode support."""
    module_obj = load_repository_module(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        module_obj,
        "AnsibleModule",
        lambda **kwargs: captured.update(kwargs) or DummyModule({}),
    )
    monkeypatch.setattr(
        module_obj,
        "OciDevopsRepositoryModule",
        lambda module: types.SimpleNamespace(
            execute_resource_module=lambda: captured.update(ran=True)
        ),
    )
    module_obj.main()
    spec = captured["argument_spec"]
    assert spec["repository_id"] == {"type": "str"}
    assert spec["project_id"] == {"type": "str"}
    assert spec["name"] == {"type": "str"}
    assert spec["description"] == {"type": "str"}
    assert spec["default_branch"] == {"type": "str"}
    assert spec["parent_repository_id"] == {"type": "str"}
    assert spec["repository_type"]["choices"] == ["hosted", "mirrored", "forked"]
    assert "default" not in spec["repository_type"]
    mirror_options = spec["mirror_repository_config"]["options"]
    assert mirror_options["connector_id"] == {"type": "str"}
    assert mirror_options["repository_url"] == {"type": "str"}
    schedule_options = mirror_options["trigger_schedule"]["options"]
    assert schedule_options["schedule_type"]["choices"] == ["none", "default", "custom"]
    assert schedule_options["custom_schedule"] == {"type": "str"}
    assert spec["state"]["choices"] == ["present", "absent"]
    assert spec["state"]["default"] == "present"
    assert spec["freeform_tags"]["type"] == "dict"
    assert spec["defined_tags"]["type"] == "dict"
    assert "compartment_id" not in spec
    assert "allow_duplicate_name" not in spec
    assert captured["supports_check_mode"] is True
    assert captured["ran"] is True


def test_main_normalizes_enum_choices_to_oci_spelling(monkeypatch):
    """Upper-case the repository type and nested schedule type before running."""
    module_obj = load_repository_module(monkeypatch)
    params = {
        "repository_type": "mirrored",
        "mirror_repository_config": {
            "connector_id": "connector1",
            "trigger_schedule": {"schedule_type": "custom"},
        },
    }
    captured = {}
    monkeypatch.setattr(
        module_obj, "AnsibleModule", lambda **kwargs: DummyModule(params)
    )
    monkeypatch.setattr(
        module_obj,
        "OciDevopsRepositoryModule",
        lambda module: captured.update(module=module)
        or types.SimpleNamespace(execute_resource_module=lambda: None),
    )
    module_obj.main()
    assert captured["module"].params["repository_type"] == "MIRRORED"
    assert (
        captured["module"].params["mirror_repository_config"]["trigger_schedule"][
            "schedule_type"
        ]
        == "CUSTOM"
    )


def test_class_metadata(monkeypatch):
    """Declare repository-specific identifier, lookup, and update metadata."""
    module_obj = load_repository_module(monkeypatch)
    cls = module_obj.OciDevopsRepositoryModule
    assert cls.resource_id_param == "repository_id"
    assert cls.resource_id_field == "id"
    assert cls.list_resource_method == "list_repositories"
    assert cls.name_response_field == "name"
    # A repository is scoped to its project, not to a compartment.
    assert cls.common_list_filter_params == ("project_id",)
    # The exact-name filter is a name-lookup optimization, not required scope,
    # so it must not appear in the scope that error messages advertise.
    assert cls.list_filter_params == ()
    assert cls.name_lookup_filter_params == ("name",)
    assert cls.create_required_fields == ("project_id", "name", "repository_type")
    assert cls.create_resource_name == "DevOps repository"
    assert cls.update_method_name == "update_repository"
    assert cls.update_details_name == "update_repository_details"
    assert cls.update_wait_states == ("ACTIVE",)
    assert cls.client_class.fget(object()).__name__ == "FakeDevopsClient"


def test_result_renames_misspelled_lifecycle_details(monkeypatch):
    """Rename the SDK's lifecyle_details field to the correct spelling."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(module_obj, {})
    result = instance.serialize_result_resource(
        FakeModel(id="r1", name="storefront", lifecyle_details="working")
    )
    assert result["lifecycle_details"] == "working"
    assert "lifecyle_details" not in result


@pytest.mark.parametrize("missing", ["project_id", "name", "repository_type"])
def test_create_requires_project_name_and_type(monkeypatch, missing):
    """Fail create validation when a required value is absent."""
    module_obj = load_repository_module(monkeypatch)
    params = {"project_id": "p1", "name": "storefront", "repository_type": "HOSTED"}
    del params[missing]
    instance = make_repository(module_obj, params)
    with pytest.raises(FailJsonCalled) as failure:
        instance.validate_create_request()
    assert missing in failure.value.payload["msg"]


def test_create_mirrored_requires_mirror_config(monkeypatch):
    """Fail a mirrored create that omits the mirror configuration."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(
        module_obj,
        {"project_id": "p1", "name": "mirror", "repository_type": "MIRRORED"},
    )
    with pytest.raises(FailJsonCalled) as failure:
        instance.validate_create_request()
    assert "mirror_repository_config" in failure.value.payload["msg"]


def test_create_mirrored_requires_repository_url(monkeypatch):
    """Fail a mirrored create whose mirror configuration has nothing to mirror."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(
        module_obj,
        {
            "project_id": "p1",
            "name": "mirror",
            "repository_type": "MIRRORED",
            "mirror_repository_config": {
                "connector_id": None,
                "repository_url": None,
                "trigger_schedule": {"schedule_type": "DEFAULT"},
            },
        },
    )
    with pytest.raises(FailJsonCalled) as failure:
        instance.validate_create_request()
    assert (
        "mirror_repository_config.repository_url" in failure.value.payload["msg"]
    )


def test_create_forked_requires_parent_repository_id(monkeypatch):
    """Fail a forked create that omits the parent repository."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(
        module_obj,
        {"project_id": "p1", "name": "fork", "repository_type": "FORKED"},
    )
    with pytest.raises(FailJsonCalled) as failure:
        instance.validate_create_request()
    assert "parent_repository_id" in failure.value.payload["msg"]


def test_create_hosted_does_not_require_dependent_options(monkeypatch):
    """Accept a hosted create without mirror or fork options."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(
        module_obj,
        {"project_id": "p1", "name": "storefront", "repository_type": "HOSTED"},
    )
    assert instance.validate_create_request() is None


def test_create_builds_details_and_waits_on_id(monkeypatch):
    """Create with CreateRepositoryDetails and wait using the repository id."""
    module_obj = load_repository_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        create_repository=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="r1"))
    )
    instance = make_repository(
        module_obj,
        {
            "wait": True,
            "project_id": "p1",
            "name": "storefront",
            "description": "desc",
            "default_branch": "main",
            "repository_type": "HOSTED",
            "freeform_tags": {"team": "ops"},
            "defined_tags": {"Ops": {"Cost": "1"}},
        },
        client,
    )
    passthrough_retry(monkeypatch, instance)
    waited = []
    monkeypatch.setattr(
        instance,
        "wait_for_resource_id",
        lambda resource_id, states: waited.append((resource_id, states))
        or FakeModel(id=resource_id),
    )
    result = instance.create_resource()
    assert result.id == "r1"
    assert waited == [("r1", ("ACTIVE",))]
    assert set(calls[0]) == {"create_repository_details"}
    assert vars(calls[0]["create_repository_details"]) == {
        "project_id": "p1",
        "name": "storefront",
        "description": "desc",
        "default_branch": "main",
        "repository_type": "HOSTED",
        "freeform_tags": {"team": "ops"},
        "defined_tags": {"Ops": {"Cost": "1"}},
    }


def test_create_mirrored_builds_nested_mirror_models(monkeypatch):
    """Build MirrorRepositoryConfig and TriggerSchedule models on create."""
    module_obj = load_repository_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        create_repository=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="r1"))
    )
    instance = make_repository(
        module_obj,
        {
            "wait": False,
            "project_id": "p1",
            "name": "mirror",
            "repository_type": "MIRRORED",
            "mirror_repository_config": {
                "connector_id": "connector1",
                "repository_url": "https://example.com/upstream.git",
                "trigger_schedule": {
                    "schedule_type": "CUSTOM",
                    "custom_schedule": "0 */4 * * *",
                },
            },
        },
        client,
    )
    passthrough_retry(monkeypatch, instance)
    instance.create_resource()
    details = vars(calls[0]["create_repository_details"])
    mirror_config = vars(details["mirror_repository_config"])
    assert mirror_config["connector_id"] == "connector1"
    assert mirror_config["repository_url"] == "https://example.com/upstream.git"
    assert vars(mirror_config["trigger_schedule"]) == {
        "schedule_type": "CUSTOM",
        "custom_schedule": "0 */4 * * *",
    }


def test_create_forked_sends_parent_repository_id(monkeypatch):
    """Send the parent repository when creating a fork."""
    module_obj = load_repository_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        create_repository=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="r1"))
    )
    instance = make_repository(
        module_obj,
        {
            "wait": False,
            "project_id": "p1",
            "name": "fork",
            "repository_type": "FORKED",
            "parent_repository_id": "parent1",
        },
        client,
    )
    passthrough_retry(monkeypatch, instance)
    instance.create_resource()
    assert (
        vars(calls[0]["create_repository_details"])["parent_repository_id"] == "parent1"
    )


def test_create_without_wait_does_not_poll(monkeypatch):
    """Return the create response directly when wait is disabled."""
    module_obj = load_repository_module(monkeypatch)
    client = types.SimpleNamespace(
        create_repository=lambda **kwargs: FakeResponse(FakeModel(id="r1"))
    )
    instance = make_repository(
        module_obj,
        {
            "wait": False,
            "project_id": "p1",
            "name": "n",
            "repository_type": "HOSTED",
        },
        client,
    )
    passthrough_retry(monkeypatch, instance)
    monkeypatch.setattr(
        instance, "wait_for_resource_id", raising(AssertionError("polled"))
    )
    assert instance.create_resource().id == "r1"


def test_create_in_check_mode_does_not_call_api(monkeypatch):
    """Report a change for a new repository without calling create."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(
        module_obj,
        {"project_id": "p1", "name": "n", "repository_type": "HOSTED"},
        types.SimpleNamespace(
            create_repository=raising(AssertionError("create in check mode"))
        ),
        check_mode=True,
    )
    monkeypatch.setattr(instance, "resolve_target_resource", lambda: None)
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_resource_module()
    assert result.value.payload["changed"] is True


def test_idempotent_present_does_not_update(monkeypatch):
    """Leave a matching repository unchanged."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(
        module_obj,
        {
            "repository_id": "r1",
            "project_id": "p1",
            "name": "storefront",
            "description": "same",
            "default_branch": "main",
            "repository_type": "HOSTED",
            "freeform_tags": {"team": "ops"},
        },
        types.SimpleNamespace(
            update_repository=raising(AssertionError("unexpected update"))
        ),
    )
    current = FakeModel(
        id="r1",
        project_id="p1",
        name="storefront",
        description="same",
        default_branch="main",
        repository_type="HOSTED",
        freeform_tags={"team": "ops"},
        defined_tags={},
    )
    monkeypatch.setattr(instance, "resolve_target_resource", lambda: current)
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_resource_module()
    assert result.value.payload["changed"] is False


def test_matching_mirror_config_is_not_an_update(monkeypatch):
    """Ignore a mirror config whose supplied fields already match."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(
        module_obj,
        {
            "mirror_repository_config": {
                "connector_id": "connector1",
                "repository_url": None,
                "trigger_schedule": {
                    "schedule_type": "DEFAULT",
                    "custom_schedule": None,
                },
            }
        },
    )
    current = FakeModel(
        id="r1",
        mirror_repository_config=FakeModel(
            connector_id="connector1",
            repository_url="https://example.com/upstream.git",
            trigger_schedule=FakeModel(
                schedule_type="DEFAULT", custom_schedule=None
            ),
        ),
    )
    assert instance.needs_update(current) is False


def test_check_mode_update_does_not_call_api(monkeypatch):
    """Predict a change in check mode without calling update."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(
        module_obj,
        {"repository_id": "r1", "description": "new"},
        types.SimpleNamespace(
            update_repository=raising(AssertionError("update in check mode"))
        ),
        check_mode=True,
    )
    current = FakeModel(id="r1", description="old", freeform_tags={}, defined_tags={})
    monkeypatch.setattr(instance, "resolve_target_resource", lambda: current)
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_resource_module()
    assert result.value.payload["changed"] is True


def test_description_update_sends_repository_id_and_details(monkeypatch):
    """Update the description by repository_id without touching other fields."""
    module_obj = load_repository_module(monkeypatch)
    calls = []
    updated = FakeModel(id="r1", description="new")
    client = types.SimpleNamespace(
        update_repository=lambda **kwargs: calls.append(kwargs) or FakeResponse(updated)
    )
    instance = make_repository(
        module_obj, {"wait": False, "repository_id": "r1", "description": "new"}, client
    )
    passthrough_retry(monkeypatch, instance)
    result = instance.update_resource(FakeModel(id="r1", description="old"))
    assert result is updated
    assert calls[0]["repository_id"] == "r1"
    assert vars(calls[0]["update_repository_details"]) == {"description": "new"}


def test_rename_by_repository_id_is_supported(monkeypatch):
    """Send a new name because OCI allows renaming a repository."""
    module_obj = load_repository_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        update_repository=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="r1"))
    )
    instance = make_repository(
        module_obj, {"wait": False, "repository_id": "r1", "name": "renamed"}, client
    )
    passthrough_retry(monkeypatch, instance)
    instance.update_resource(FakeModel(id="r1", name="original"))
    assert vars(calls[0]["update_repository_details"]) == {"name": "renamed"}


def test_default_branch_and_type_update(monkeypatch):
    """Send the default branch and repository type when they drift."""
    module_obj = load_repository_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        update_repository=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="r1"))
    )
    instance = make_repository(
        module_obj,
        {
            "wait": False,
            "repository_id": "r1",
            "default_branch": "main",
            "repository_type": "HOSTED",
        },
        client,
    )
    passthrough_retry(monkeypatch, instance)
    instance.update_resource(
        FakeModel(id="r1", default_branch="master", repository_type="MIRRORED")
    )
    assert vars(calls[0]["update_repository_details"]) == {
        "default_branch": "main",
        "repository_type": "HOSTED",
    }


def test_mirror_config_update_builds_nested_models(monkeypatch):
    """Send MirrorRepositoryConfig models when the mirror config changes."""
    module_obj = load_repository_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        update_repository=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="r1"))
    )
    instance = make_repository(
        module_obj,
        {
            "wait": False,
            "repository_id": "r1",
            "mirror_repository_config": {
                "connector_id": "connector2",
                "trigger_schedule": {"schedule_type": "NONE"},
            },
        },
        client,
    )
    passthrough_retry(monkeypatch, instance)
    current = FakeModel(
        id="r1",
        mirror_repository_config=FakeModel(
            connector_id="connector1",
            trigger_schedule=FakeModel(schedule_type="DEFAULT"),
        ),
    )
    instance.update_resource(current)
    details = vars(calls[0]["update_repository_details"])
    mirror_config = vars(details["mirror_repository_config"])
    assert mirror_config["connector_id"] == "connector2"
    assert vars(mirror_config["trigger_schedule"]) == {"schedule_type": "NONE"}


def test_partial_mirror_config_update_keeps_current_fields(monkeypatch):
    """Merge a partial mirror config onto the current one before updating.

    OCI replaces mirrorRepositoryConfig wholesale, so sending only the supplied
    sub-fields would clear the connector and URL the caller never mentioned.
    """
    module_obj = load_repository_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        update_repository=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="r1"))
    )
    instance = make_repository(
        module_obj,
        {
            "wait": False,
            "repository_id": "r1",
            "mirror_repository_config": {
                "connector_id": None,
                "repository_url": None,
                "trigger_schedule": {
                    "schedule_type": "CUSTOM",
                    "custom_schedule": "0 * * * *",
                },
            },
        },
        client,
    )
    passthrough_retry(monkeypatch, instance)
    current = FakeModel(
        id="r1",
        mirror_repository_config=FakeModel(
            connector_id="connector1",
            repository_url="https://example.com/upstream.git",
            trigger_schedule=FakeModel(
                schedule_type="DEFAULT", custom_schedule=None
            ),
        ),
    )
    instance.update_resource(current)
    details = vars(calls[0]["update_repository_details"])
    mirror_config = vars(details["mirror_repository_config"])
    assert mirror_config["connector_id"] == "connector1"
    assert mirror_config["repository_url"] == "https://example.com/upstream.git"
    assert vars(mirror_config["trigger_schedule"]) == {
        "schedule_type": "CUSTOM",
        "custom_schedule": "0 * * * *",
    }


def test_update_waits_on_repository_id(monkeypatch):
    """Poll the updated repository by id when wait is enabled."""
    module_obj = load_repository_module(monkeypatch)
    client = types.SimpleNamespace(
        update_repository=lambda **kwargs: FakeResponse(FakeModel(id="r1"))
    )
    instance = make_repository(module_obj, {"wait": True, "description": "new"}, client)
    passthrough_retry(monkeypatch, instance)
    waited = []
    monkeypatch.setattr(
        instance,
        "wait_for_resource_id",
        lambda resource_id, states: waited.append((resource_id, states))
        or FakeModel(id=resource_id),
    )
    instance.update_resource(FakeModel(id="r1", description="old"))
    assert waited == [("r1", ("ACTIVE",))]


def test_tags_only_update_sends_only_tags(monkeypatch):
    """Send just the tag fields when nothing else drifted."""
    module_obj = load_repository_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        update_repository=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="r1"))
    )
    instance = make_repository(
        module_obj,
        {"wait": False, "repository_id": "r1", "freeform_tags": {"team": "new"}},
        client,
    )
    passthrough_retry(monkeypatch, instance)
    current = FakeModel(id="r1", description="keep me", freeform_tags={"team": "old"})
    instance.update_resource(current)
    assert vars(calls[0]["update_repository_details"]) == {
        "freeform_tags": {"team": "new"}
    }


def test_no_change_plan_is_empty(monkeypatch):
    """Report no planned fields when nothing changes."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(module_obj, {"freeform_tags": {"a": "b"}})
    plan = instance.build_update_plan(
        FakeModel(id="r1", description="d", freeform_tags={"a": "b"})
    )
    assert plan["update_model_fields"] == {}
    assert plan["update_needed"] is False


@pytest.mark.parametrize(
    "params, current, field",
    [
        ({"project_id": "other"}, FakeModel(project_id="p1"), "project_id"),
        (
            {"parent_repository_id": "other"},
            FakeModel(parent_repository_id="parent1"),
            "parent_repository_id",
        ),
    ],
)
def test_immutable_fields_fail(monkeypatch, params, current, field):
    """Fail when the project or parent repository would change."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(module_obj, params)
    with pytest.raises(FailJsonCalled) as failure:
        instance.needs_update(current)
    assert field in failure.value.payload["msg"]


def test_get_by_repository_id_404_is_missing(monkeypatch):
    """Treat a 404 from get_repository as a missing repository."""
    module_obj = load_repository_module(monkeypatch)
    missing = RuntimeError("missing")
    missing.status = 404
    client = types.SimpleNamespace(get_repository=raising(missing))
    instance = make_repository(module_obj, {"repository_id": "r1"}, client)
    passthrough_retry(monkeypatch, instance)
    assert instance.resolve_target_resource() is None


def test_deleted_repository_is_treated_as_missing(monkeypatch):
    """Ignore a tombstoned repository so present recreates instead of updating."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(module_obj, {"repository_id": "r1"})
    monkeypatch.setattr(
        instance,
        "get_resource_by_id",
        lambda resource_id: FakeModel(id=resource_id, lifecycle_state="DELETED"),
    )
    assert instance.resolve_target_resource() is None


def test_get_resource_response_uses_repository_id(monkeypatch):
    """Call get_repository with the repository_id keyword."""
    module_obj = load_repository_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        get_repository=lambda **kwargs: calls.append(kwargs) or "response"
    )
    instance = make_repository(module_obj, {}, client)
    passthrough_retry(monkeypatch, instance)
    assert instance.get_resource_response("r1") == "response"
    assert calls == [{"repository_id": "r1"}]


def test_name_lookup_is_scoped_by_project(monkeypatch):
    """Scope name lookup to list_repositories by project and server-side name."""
    module_obj = load_repository_module(monkeypatch)
    client = types.SimpleNamespace(list_repositories=object())
    instance = make_repository(
        module_obj, {"name": "storefront", "project_id": "p1"}, client
    )
    calls = []
    monkeypatch.setattr(
        instance,
        "list_all_resources",
        lambda method, **kwargs: calls.append((method, kwargs)) or [],
    )
    assert instance.find_resources_by_name() == []
    assert calls == [
        (client.list_repositories, {"project_id": "p1", "name": "storefront"})
    ]


def test_name_lookup_without_project_fails(monkeypatch):
    """Require the project when resolving a repository by name."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(module_obj, {"name": "storefront"})
    with pytest.raises(FailJsonCalled) as failure:
        instance.find_resources_by_name()
    assert "project_id" in failure.value.payload["msg"]


def test_name_lookup_rehydrates_summary_to_full_model(monkeypatch):
    """Re-fetch a name-matched summary so results match the get_repository shape."""
    module_obj = load_repository_module(monkeypatch)
    client = types.SimpleNamespace(list_repositories=object())
    instance = make_repository(
        module_obj, {"name": "storefront", "project_id": "p1"}, client
    )
    summary = FakeModel(id="r1", name="storefront")
    full = FakeModel(id="r1", name="storefront", commit_count=7)
    monkeypatch.setattr(
        instance, "list_all_resources", lambda method, **kwargs: [summary]
    )
    monkeypatch.setattr(
        instance,
        "get_resource_by_id",
        lambda resource_id: full if resource_id == "r1" else None,
    )
    assert instance.resolve_target_resource() is full


def test_name_lookup_falls_back_to_summary_when_refetch_misses(monkeypatch):
    """Keep the summary when the re-fetch finds nothing."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(module_obj, {"name": "storefront", "project_id": "p1"})
    summary = FakeModel(id="r1", name="storefront")
    monkeypatch.setattr(instance, "get_resource_by_id", lambda resource_id: None)
    assert instance.hydrate_named_resource(summary) is summary


def test_delete_calls_delete_repository_and_waits(monkeypatch):
    """Delete by repository_id and wait for the repository to disappear."""
    module_obj = load_repository_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        delete_repository=lambda **kwargs: calls.append(kwargs) or FakeResponse(None)
    )
    instance = make_repository(module_obj, {"wait": True}, client)
    passthrough_retry(monkeypatch, instance)
    waited = []
    monkeypatch.setattr(
        instance,
        "wait_for_resource_id",
        lambda resource_id, states: waited.append((resource_id, states)) or None,
    )
    instance.delete_resource(FakeModel(id="r1"))
    assert calls == [{"repository_id": "r1"}]
    assert len(waited) == 1
    assert waited[0][0] == "r1"
    assert "DELETED" in waited[0][1]


def test_delete_conflict_reports_dependent_resources(monkeypatch):
    """Explain a 409 from delete_repository as blocked by dependent resources."""
    module_obj = load_repository_module(monkeypatch)
    conflict = RuntimeError("children exist")
    conflict.status = 409
    client = types.SimpleNamespace(delete_repository=raising(conflict))
    instance = make_repository(module_obj, {"wait": False}, client)
    passthrough_retry(monkeypatch, instance)
    with pytest.raises(FailJsonCalled) as failure:
        instance.delete_resource(FakeModel(id="r1"))
    assert "dependent resources" in failure.value.payload["msg"]


def test_absent_without_id_or_name_fails(monkeypatch):
    """Require an identifier before attempting a delete."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(module_obj, {"state": "absent"})
    with pytest.raises(FailJsonCalled) as failure:
        instance.validate_delete_request()
    message = failure.value.payload["msg"]
    assert "repository_id" in message
    assert "name (with project_id)" in message


def test_absent_when_missing_is_unchanged(monkeypatch):
    """Report no change when the repository does not exist."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(
        module_obj,
        {"state": "absent", "repository_id": "r1"},
        types.SimpleNamespace(
            delete_repository=raising(AssertionError("unexpected delete"))
        ),
    )
    monkeypatch.setattr(instance, "resolve_target_resource", lambda: None)
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_resource_module()
    assert result.value.payload["changed"] is False


def test_absent_in_check_mode_does_not_delete(monkeypatch):
    """Report a change in check mode without calling delete."""
    module_obj = load_repository_module(monkeypatch)
    instance = make_repository(
        module_obj,
        {"state": "absent", "repository_id": "r1"},
        types.SimpleNamespace(
            delete_repository=raising(AssertionError("delete in check mode"))
        ),
        check_mode=True,
    )
    monkeypatch.setattr(
        instance, "resolve_target_resource", lambda: FakeModel(id="r1")
    )
    monkeypatch.setattr(
        instance, "delete_resource", raising(AssertionError("delete in check mode"))
    )
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_resource_module()
    assert result.value.payload["changed"] is True
