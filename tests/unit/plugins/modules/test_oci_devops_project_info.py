from __future__ import absolute_import, division, print_function
__metaclass__ = type

import types

import pytest

from .conftest import (
    DummyModule,
    ExitJsonCalled,
    FakeModel,
    install_fake_oci as shared_install_fake_oci,
    load_collection_module,
    make_module_instance,
    raising,
)


def install_fake_oci(monkeypatch):
    """Install the shared fake OCI SDK with a DevOps namespace."""
    oci_module, service_error = shared_install_fake_oci(monkeypatch)
    oci_module.devops = types.SimpleNamespace(
        DevopsClient=type("FakeDevopsClient", (), {}),
        models=types.SimpleNamespace(),
    )
    return oci_module, service_error


def load_project_info_module(monkeypatch):
    """Load the project info module with a fake OCI SDK."""
    install_fake_oci(monkeypatch)
    return load_collection_module("oci_devops_project_info")


def make_project_info(module_obj, params, client=None):
    """Create an info module instance without initializing OCI credentials."""
    return make_module_instance(
        module_obj,
        "OciDevopsProjectInfoModule",
        params,
        client=client,
    )


def test_main_argument_spec_contract(monkeypatch):
    """Expose project filters, lowercase lifecycle choices, and required_one_of."""
    module_obj = load_project_info_module(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        module_obj,
        "AnsibleModule",
        lambda **kwargs: captured.update(kwargs)
        or DummyModule({"lifecycle_state": "needs_attention"}),
    )
    monkeypatch.setattr(
        module_obj,
        "OciDevopsProjectInfoModule",
        lambda module: captured.update(module=module)
        or types.SimpleNamespace(execute_info_module=lambda: None),
    )
    module_obj.main()
    assert captured["module"].params["lifecycle_state"] == "NEEDS_ATTENTION"
    assert captured["required_one_of"] == [["compartment_id", "project_id"]]
    assert captured["supports_check_mode"] is True
    spec = captured["argument_spec"]
    assert spec["project_id"] == {"type": "str"}
    assert spec["compartment_id"] == {"type": "str"}
    assert spec["name"] == {"type": "str"}
    assert spec["lifecycle_state"]["choices"] == [
        "creating",
        "updating",
        "active",
        "deleting",
        "deleted",
        "failed",
        "needs_attention",
    ]


def test_class_metadata_and_client_class(monkeypatch):
    """Declare the DevOps client and get/list metadata."""
    module_obj = load_project_info_module(monkeypatch)
    module_class = module_obj.OciDevopsProjectInfoModule
    assert module_class.results_key == "projects"
    assert module_class.resource_id_param == "project_id"
    assert module_class.resource_get_method == "get_project"
    assert module_class.list_resource_method == "list_projects"
    assert module_class.name_response_field == "name"
    assert module_class.list_filter_params == (
        "compartment_id",
        "lifecycle_state",
        "name",
    )
    instance = make_project_info(module_obj, {})
    assert instance.client_class is module_obj.oci.devops.DevopsClient


def test_get_by_project_id_and_serialization(monkeypatch):
    """Fetch a project by id and serialize its nested notification config."""
    module_obj = load_project_info_module(monkeypatch)
    project = FakeModel(
        id="project1",
        name="builds",
        compartment_id="compartment1",
        description="build pipelines",
        namespace="examplens",
        notification_config=FakeModel(topic_id="topic1"),
        lifecycle_state="ACTIVE",
        freeform_tags={"team": "ops"},
    )
    client = types.SimpleNamespace(get_project=object(), list_projects=object())
    instance = make_project_info(module_obj, {"project_id": "project1"}, client)
    calls = []
    monkeypatch.setattr(
        instance,
        "get_resource_by_id",
        lambda resource_id, method, **kwargs: calls.append(
            (resource_id, method, kwargs)
        )
        or [project],
    )
    assert instance.fetch_resources() == [project]
    assert calls == [("project1", client.get_project, {"project_id": "project1"})]
    result = instance.serialize_result_resource(project)
    assert result["id"] == "project1"
    assert result["name"] == "builds"
    assert result["notification_config"] == {"topic_id": "topic1"}
    assert result["freeform_tags"] == {"team": "ops"}


def test_get_404_returns_empty_and_other_errors_propagate(monkeypatch):
    """Return no projects for a missing id and raise other OCI errors."""
    module_obj = load_project_info_module(monkeypatch)
    instance = make_project_info(
        module_obj, {"project_id": "p"}, types.SimpleNamespace(get_project=object())
    )
    missing = RuntimeError("missing")
    missing.status = 404
    monkeypatch.setattr(instance, "call_with_retry", raising(missing))
    assert instance.fetch_resources() == []
    forbidden = RuntimeError("forbidden")
    forbidden.status = 403
    monkeypatch.setattr(instance, "call_with_retry", raising(forbidden))
    with pytest.raises(RuntimeError, match="forbidden"):
        instance.fetch_resources()


def test_list_scoped_by_compartment_lifecycle_and_name(monkeypatch):
    """Pass SDK-cased list filters to OCI and keep only exact name matches."""
    module_obj = load_project_info_module(monkeypatch)
    client = types.SimpleNamespace(list_projects=object())
    instance = make_project_info(
        module_obj,
        {
            "compartment_id": "compartment1",
            "lifecycle_state": "ACTIVE",
            "name": "builds",
        },
        client,
    )
    matching = FakeModel(name="builds", id="p1")
    other = FakeModel(name="builds-old", id="p2")
    calls = []
    monkeypatch.setattr(
        instance,
        "list_all_resources",
        lambda method, **kwargs: calls.append((method, kwargs)) or [matching, other],
    )
    assert instance.fetch_resources() == [matching]
    assert calls == [
        (
            client.list_projects,
            {
                "compartment_id": "compartment1",
                "lifecycle_state": "ACTIVE",
                "name": "builds",
            },
        )
    ]


def test_info_result_is_unchanged_and_reports_projects(monkeypatch):
    """Return serialized projects under projects with changed set to false."""
    module_obj = load_project_info_module(monkeypatch)
    instance = make_project_info(module_obj, {})
    monkeypatch.setattr(
        instance,
        "fetch_resources",
        lambda: [FakeModel(id="p", name="builds", lifecycle_state="ACTIVE")],
    )
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_info_module()
    assert result.value.payload["changed"] is False
    assert result.value.payload["projects"] == [
        {"id": "p", "name": "builds", "lifecycle_state": "ACTIVE"}
    ]
