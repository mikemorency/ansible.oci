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


PROJECT_MODEL_NAMES = (
    "CreateProjectDetails",
    "UpdateProjectDetails",
    "NotificationConfig",
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
            **{model_name: FakeModel for model_name in PROJECT_MODEL_NAMES}
        ),
    )
    return oci_module, service_error


def load_project_module(monkeypatch):
    """Load the DevOps project module with fake OCI types.

    Args:
        monkeypatch: Pytest fixture for replacing OCI modules.

    Returns:
        The loaded project module.
    """
    install_fake_oci(monkeypatch)
    return load_collection_module("oci_devops_project")


def make_project(module_obj, params, client=None, check_mode=False):
    """Create a project module instance without OCI credentials.

    Args:
        module_obj: The loaded project module.
        params: The parameters for the module instance.
        client: An optional fake client.
        check_mode: Whether Ansible check mode is enabled.

    Returns:
        The project module instance.
    """
    return make_module_instance(
        module_obj,
        "OciDevopsProjectModule",
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
    """Expose the project options and run the module with check mode support."""
    module_obj = load_project_module(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        module_obj,
        "AnsibleModule",
        lambda **kwargs: captured.update(kwargs) or DummyModule({}),
    )
    monkeypatch.setattr(
        module_obj,
        "OciDevopsProjectModule",
        lambda module: types.SimpleNamespace(
            execute_resource_module=lambda: captured.update(ran=True)
        ),
    )
    module_obj.main()
    spec = captured["argument_spec"]
    assert spec["project_id"] == {"type": "str"}
    assert spec["name"] == {"type": "str"}
    assert spec["compartment_id"] == {"type": "str"}
    assert spec["description"] == {"type": "str"}
    assert spec["notification_config"]["type"] == "dict"
    assert spec["notification_config"]["options"]["topic_id"] == {
        "type": "str",
        "required": True,
    }
    assert spec["state"]["choices"] == ["present", "absent"]
    assert spec["state"]["default"] == "present"
    assert spec["freeform_tags"]["type"] == "dict"
    assert spec["defined_tags"]["type"] == "dict"
    assert "allow_duplicate_name" not in spec
    assert captured["supports_check_mode"] is True
    assert captured["ran"] is True


def test_class_metadata(monkeypatch):
    """Declare project-specific identifier, lookup, and update metadata."""
    module_obj = load_project_module(monkeypatch)
    cls = module_obj.OciDevopsProjectModule
    assert cls.resource_id_param == "project_id"
    assert cls.resource_id_field == "id"
    assert cls.list_resource_method == "list_projects"
    assert cls.name_response_field == "name"
    assert cls.create_required_fields == (
        "compartment_id",
        "name",
        "notification_config",
    )
    assert cls.create_resource_name == "DevOps project"
    assert cls.update_method_name == "update_project"
    assert cls.update_details_name == "update_project_details"
    assert cls.update_wait_states == ("ACTIVE",)
    assert cls.client_class.fget(object()).__name__ == "FakeDevopsClient"


@pytest.mark.parametrize("missing", ["compartment_id", "name", "notification_config"])
def test_create_requires_compartment_name_and_notification(monkeypatch, missing):
    """Fail create validation when a required value is absent."""
    module_obj = load_project_module(monkeypatch)
    params = {
        "compartment_id": "c",
        "name": "project",
        "notification_config": {"topic_id": "t1"},
    }
    del params[missing]
    instance = make_project(module_obj, params)
    with pytest.raises(FailJsonCalled) as failure:
        instance.validate_create_request()
    assert missing in failure.value.payload["msg"]


def test_create_builds_details_and_waits_on_id(monkeypatch):
    """Create with CreateProjectDetails and wait using the project id."""
    module_obj = load_project_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        create_project=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="p1"))
    )
    instance = make_project(
        module_obj,
        {
            "wait": True,
            "compartment_id": "c1",
            "name": "builds",
            "description": "desc",
            "notification_config": {"topic_id": "t1"},
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
    assert result.id == "p1"
    assert waited == [("p1", ("ACTIVE",))]
    assert set(calls[0]) == {"create_project_details"}
    details = vars(calls[0]["create_project_details"])
    notification_config = details.pop("notification_config")
    assert vars(notification_config) == {"topic_id": "t1"}
    assert details == {
        "compartment_id": "c1",
        "name": "builds",
        "description": "desc",
        "freeform_tags": {"team": "ops"},
        "defined_tags": {"Ops": {"Cost": "1"}},
    }


def test_create_without_wait_does_not_poll(monkeypatch):
    """Return the create response directly when wait is disabled."""
    module_obj = load_project_module(monkeypatch)
    client = types.SimpleNamespace(
        create_project=lambda **kwargs: FakeResponse(FakeModel(id="p1"))
    )
    instance = make_project(
        module_obj,
        {
            "wait": False,
            "compartment_id": "c",
            "name": "n",
            "notification_config": {"topic_id": "t1"},
        },
        client,
    )
    passthrough_retry(monkeypatch, instance)
    monkeypatch.setattr(
        instance, "wait_for_resource_id", raising(AssertionError("polled"))
    )
    assert instance.create_resource().id == "p1"


def test_create_in_check_mode_does_not_call_api(monkeypatch):
    """Report a change for a new project without calling create."""
    module_obj = load_project_module(monkeypatch)
    instance = make_project(
        module_obj,
        {
            "compartment_id": "c",
            "name": "n",
            "notification_config": {"topic_id": "t1"},
        },
        types.SimpleNamespace(
            create_project=raising(AssertionError("create in check mode"))
        ),
        check_mode=True,
    )
    monkeypatch.setattr(instance, "resolve_target_resource", lambda: None)
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_resource_module()
    assert result.value.payload["changed"] is True


def test_idempotent_present_does_not_update(monkeypatch):
    """Leave a matching project unchanged."""
    module_obj = load_project_module(monkeypatch)
    instance = make_project(
        module_obj,
        {
            "project_id": "p1",
            "name": "n",
            "compartment_id": "c",
            "description": "same",
            "notification_config": {"topic_id": "t1"},
            "freeform_tags": {"team": "ops"},
        },
        types.SimpleNamespace(
            update_project=raising(AssertionError("unexpected update"))
        ),
    )
    current = FakeModel(
        id="p1",
        name="n",
        compartment_id="c",
        description="same",
        notification_config=FakeModel(topic_id="t1"),
        freeform_tags={"team": "ops"},
        defined_tags={},
    )
    monkeypatch.setattr(instance, "resolve_target_resource", lambda: current)
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_resource_module()
    assert result.value.payload["changed"] is False


def test_check_mode_update_does_not_call_api(monkeypatch):
    """Predict a change in check mode without calling update."""
    module_obj = load_project_module(monkeypatch)
    instance = make_project(
        module_obj,
        {"project_id": "p1", "description": "new"},
        types.SimpleNamespace(
            update_project=raising(AssertionError("update in check mode"))
        ),
        check_mode=True,
    )
    current = FakeModel(id="p1", description="old", freeform_tags={}, defined_tags={})
    monkeypatch.setattr(instance, "resolve_target_resource", lambda: current)
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_resource_module()
    assert result.value.payload["changed"] is True


def test_description_update_sends_project_id_and_details(monkeypatch):
    """Update the description by project_id without touching other fields."""
    module_obj = load_project_module(monkeypatch)
    calls = []
    updated = FakeModel(id="p1", description="new")
    client = types.SimpleNamespace(
        update_project=lambda **kwargs: calls.append(kwargs) or FakeResponse(updated)
    )
    instance = make_project(
        module_obj, {"wait": False, "project_id": "p1", "description": "new"}, client
    )
    passthrough_retry(monkeypatch, instance)
    result = instance.update_resource(FakeModel(id="p1", description="old"))
    assert result is updated
    assert calls[0]["project_id"] == "p1"
    assert vars(calls[0]["update_project_details"]) == {"description": "new"}


def test_notification_topic_update_builds_nested_model(monkeypatch):
    """Send a NotificationConfig model when the topic changes."""
    module_obj = load_project_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        update_project=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="p1"))
    )
    instance = make_project(
        module_obj,
        {
            "wait": False,
            "project_id": "p1",
            "notification_config": {"topic_id": "t2"},
        },
        client,
    )
    passthrough_retry(monkeypatch, instance)
    current = FakeModel(id="p1", notification_config=FakeModel(topic_id="t1"))
    instance.update_resource(current)
    details = vars(calls[0]["update_project_details"])
    assert vars(details["notification_config"]) == {"topic_id": "t2"}


def test_matching_notification_topic_is_not_an_update(monkeypatch):
    """Ignore a notification config that already matches the project."""
    module_obj = load_project_module(monkeypatch)
    instance = make_project(
        module_obj, {"notification_config": {"topic_id": "t1"}}
    )
    current = FakeModel(id="p1", notification_config=FakeModel(topic_id="t1"))
    assert instance.needs_update(current) is False


def test_update_waits_on_project_id(monkeypatch):
    """Poll the updated project by id when wait is enabled."""
    module_obj = load_project_module(monkeypatch)
    client = types.SimpleNamespace(
        update_project=lambda **kwargs: FakeResponse(FakeModel(id="p1"))
    )
    instance = make_project(module_obj, {"wait": True, "description": "new"}, client)
    passthrough_retry(monkeypatch, instance)
    waited = []
    monkeypatch.setattr(
        instance,
        "wait_for_resource_id",
        lambda resource_id, states: waited.append((resource_id, states))
        or FakeModel(id=resource_id),
    )
    instance.update_resource(FakeModel(id="p1", description="old"))
    assert waited == [("p1", ("ACTIVE",))]


def test_tags_only_update_sends_only_tags(monkeypatch):
    """Send just the tag fields when nothing else drifted."""
    module_obj = load_project_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        update_project=lambda **kwargs: calls.append(kwargs)
        or FakeResponse(FakeModel(id="p1"))
    )
    instance = make_project(
        module_obj,
        {"wait": False, "project_id": "p1", "freeform_tags": {"team": "new"}},
        client,
    )
    passthrough_retry(monkeypatch, instance)
    current = FakeModel(id="p1", description="keep me", freeform_tags={"team": "old"})
    instance.update_resource(current)
    assert vars(calls[0]["update_project_details"]) == {
        "freeform_tags": {"team": "new"}
    }


def test_no_change_plan_is_empty(monkeypatch):
    """Report no planned fields when nothing changes."""
    module_obj = load_project_module(monkeypatch)
    instance = make_project(module_obj, {"freeform_tags": {"a": "b"}})
    plan = instance.build_update_plan(
        FakeModel(id="p1", description="d", freeform_tags={"a": "b"})
    )
    assert plan["update_model_fields"] == {}
    assert plan["update_needed"] is False


@pytest.mark.parametrize(
    "params, current, field",
    [
        ({"name": "new"}, FakeModel(name="old"), "name"),
        ({"compartment_id": "other"}, FakeModel(compartment_id="c1"), "compartment_id"),
    ],
)
def test_immutable_fields_fail(monkeypatch, params, current, field):
    """Fail when the name or compartment would change."""
    module_obj = load_project_module(monkeypatch)
    instance = make_project(module_obj, params)
    with pytest.raises(FailJsonCalled) as failure:
        instance.needs_update(current)
    assert field in failure.value.payload["msg"]


def test_get_by_project_id_404_is_missing(monkeypatch):
    """Treat a 404 from get_project as a missing project."""
    module_obj = load_project_module(monkeypatch)
    missing = RuntimeError("missing")
    missing.status = 404
    client = types.SimpleNamespace(get_project=raising(missing))
    instance = make_project(module_obj, {"project_id": "p1"}, client)
    passthrough_retry(monkeypatch, instance)
    assert instance.resolve_target_resource() is None


def test_deleted_project_is_treated_as_missing(monkeypatch):
    """Ignore a tombstoned project so present recreates instead of updating."""
    module_obj = load_project_module(monkeypatch)
    instance = make_project(module_obj, {"project_id": "p1"})
    monkeypatch.setattr(
        instance,
        "get_resource_by_id",
        lambda resource_id: FakeModel(id=resource_id, lifecycle_state="DELETED"),
    )
    assert instance.resolve_target_resource() is None


def test_get_resource_response_uses_project_id(monkeypatch):
    """Call get_project with the project_id keyword."""
    module_obj = load_project_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        get_project=lambda **kwargs: calls.append(kwargs) or "response"
    )
    instance = make_project(module_obj, {}, client)
    passthrough_retry(monkeypatch, instance)
    assert instance.get_resource_response("p1") == "response"
    assert calls == [{"project_id": "p1"}]


def test_name_lookup_is_scoped_by_compartment(monkeypatch):
    """Scope name lookup to list_projects by compartment and server-side name filter."""
    module_obj = load_project_module(monkeypatch)
    client = types.SimpleNamespace(list_projects=object())
    instance = make_project(module_obj, {"name": "builds", "compartment_id": "c1"}, client)
    calls = []
    monkeypatch.setattr(
        instance,
        "list_all_resources",
        lambda method, **kwargs: calls.append((method, kwargs)) or [],
    )
    assert instance.find_resources_by_name() == []
    assert calls == [(client.list_projects, {"compartment_id": "c1", "name": "builds"})]


def test_name_lookup_without_compartment_fails(monkeypatch):
    """Require the compartment when resolving a project by name."""
    module_obj = load_project_module(monkeypatch)
    instance = make_project(module_obj, {"name": "builds"})
    with pytest.raises(FailJsonCalled) as failure:
        instance.find_resources_by_name()
    assert "compartment_id" in failure.value.payload["msg"]


def test_name_lookup_matches_name_field(monkeypatch):
    """Resolve a project by its name response field."""
    module_obj = load_project_module(monkeypatch)
    client = types.SimpleNamespace(list_projects=object())
    instance = make_project(module_obj, {"name": "builds", "compartment_id": "c1"}, client)
    projects = [
        FakeModel(id="p0", name="other"),
        FakeModel(id="p1", name="builds"),
    ]
    monkeypatch.setattr(instance, "list_all_resources", lambda method, **kwargs: projects)
    assert instance.resolve_target_resource().id == "p1"


def test_delete_calls_delete_project_and_waits(monkeypatch):
    """Delete by project_id and wait for the project to disappear."""
    module_obj = load_project_module(monkeypatch)
    calls = []
    client = types.SimpleNamespace(
        delete_project=lambda **kwargs: calls.append(kwargs) or FakeResponse(None)
    )
    instance = make_project(module_obj, {"wait": True}, client)
    passthrough_retry(monkeypatch, instance)
    waited = []
    monkeypatch.setattr(
        instance,
        "wait_for_resource_id",
        lambda resource_id, states: waited.append((resource_id, states)) or None,
    )
    instance.delete_resource(FakeModel(id="p1"))
    assert calls == [{"project_id": "p1"}]
    assert len(waited) == 1
    assert waited[0][0] == "p1"
    assert "DELETED" in waited[0][1]


def test_delete_conflict_reports_dependent_resources(monkeypatch):
    """Explain a 409 from delete_project as blocked by dependent resources."""
    module_obj = load_project_module(monkeypatch)
    conflict = RuntimeError("children exist")
    conflict.status = 409
    client = types.SimpleNamespace(delete_project=raising(conflict))
    instance = make_project(module_obj, {"wait": False}, client)
    passthrough_retry(monkeypatch, instance)
    with pytest.raises(FailJsonCalled) as failure:
        instance.delete_resource(FakeModel(id="p1"))
    assert "dependent resources" in failure.value.payload["msg"]


def test_absent_when_missing_is_unchanged(monkeypatch):
    """Report no change when the project does not exist."""
    module_obj = load_project_module(monkeypatch)
    instance = make_project(
        module_obj,
        {"state": "absent", "project_id": "p1"},
        types.SimpleNamespace(
            delete_project=raising(AssertionError("unexpected delete"))
        ),
    )
    monkeypatch.setattr(instance, "resolve_target_resource", lambda: None)
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_resource_module()
    assert result.value.payload["changed"] is False


def test_absent_in_check_mode_does_not_delete(monkeypatch):
    """Report a change in check mode without calling delete."""
    module_obj = load_project_module(monkeypatch)
    instance = make_project(
        module_obj,
        {"state": "absent", "project_id": "p1"},
        types.SimpleNamespace(
            delete_project=raising(AssertionError("delete in check mode"))
        ),
        check_mode=True,
    )
    monkeypatch.setattr(
        instance, "resolve_target_resource", lambda: FakeModel(id="p1")
    )
    monkeypatch.setattr(
        instance, "delete_resource", raising(AssertionError("delete in check mode"))
    )
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_resource_module()
    assert result.value.payload["changed"] is True
