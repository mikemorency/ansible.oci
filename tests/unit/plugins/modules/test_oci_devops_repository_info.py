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


def load_repository_info_module(monkeypatch):
    """Load the repository info module with a fake OCI SDK."""
    install_fake_oci(monkeypatch)
    return load_collection_module("oci_devops_repository_info")


def make_repository_info(module_obj, params, client=None):
    """Create an info module instance without initializing OCI credentials."""
    return make_module_instance(
        module_obj,
        "OciDevopsRepositoryInfoModule",
        params,
        client=client,
    )


def test_main_argument_spec_contract(monkeypatch):
    """Expose repository filters, lowercase lifecycle choices, and required_one_of."""
    module_obj = load_repository_info_module(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        module_obj,
        "AnsibleModule",
        lambda **kwargs: captured.update(kwargs)
        or DummyModule({"lifecycle_state": "deleting"}),
    )
    monkeypatch.setattr(
        module_obj,
        "OciDevopsRepositoryInfoModule",
        lambda module: captured.update(module=module)
        or types.SimpleNamespace(execute_info_module=lambda: None),
    )
    module_obj.main()
    assert captured["module"].params["lifecycle_state"] == "DELETING"
    assert captured["required_one_of"] == [
        ["compartment_id", "project_id", "repository_id"]
    ]
    assert captured["supports_check_mode"] is True
    spec = captured["argument_spec"]
    assert spec["repository_id"] == {"type": "str"}
    assert spec["project_id"] == {"type": "str"}
    assert spec["compartment_id"] == {"type": "str"}
    assert spec["name"] == {"type": "str"}
    # list_repositories does not accept UPDATING or NEEDS_ATTENTION.
    assert spec["lifecycle_state"]["choices"] == [
        "creating",
        "active",
        "deleting",
        "deleted",
        "failed",
    ]


def test_class_metadata_and_client_class(monkeypatch):
    """Declare the DevOps client and get/list metadata."""
    module_obj = load_repository_info_module(monkeypatch)
    module_class = module_obj.OciDevopsRepositoryInfoModule
    assert module_class.results_key == "repositories"
    assert module_class.resource_id_param == "repository_id"
    assert module_class.resource_get_method == "get_repository"
    assert module_class.list_resource_method == "list_repositories"
    assert module_class.name_response_field == "name"
    assert module_class.list_filter_params == (
        "compartment_id",
        "project_id",
        "lifecycle_state",
        "name",
    )
    instance = make_repository_info(module_obj, {})
    assert instance.client_class is module_obj.oci.devops.DevopsClient


def test_get_by_repository_id_and_serialization(monkeypatch):
    """Fetch a repository by id and serialize its nested mirror config."""
    module_obj = load_repository_info_module(monkeypatch)
    repository = FakeModel(
        id="repository1",
        name="storefront",
        project_id="project1",
        compartment_id="compartment1",
        description="storefront source",
        default_branch="main",
        repository_type="MIRRORED",
        http_url="https://example.com/storefront.git",
        mirror_repository_config=FakeModel(
            connector_id="connector1",
            repository_url="https://example.com/upstream.git",
            trigger_schedule=FakeModel(schedule_type="DEFAULT"),
        ),
        lifecycle_state="ACTIVE",
        freeform_tags={"team": "ops"},
    )
    client = types.SimpleNamespace(get_repository=object(), list_repositories=object())
    instance = make_repository_info(
        module_obj, {"repository_id": "repository1"}, client
    )
    calls = []
    monkeypatch.setattr(
        instance,
        "get_resource_by_id",
        lambda resource_id, method, **kwargs: calls.append(
            (resource_id, method, kwargs)
        )
        or [repository],
    )
    assert instance.fetch_resources() == [repository]
    assert calls == [
        ("repository1", client.get_repository, {"repository_id": "repository1"})
    ]
    result = instance.serialize_result_resource(repository)
    assert result["id"] == "repository1"
    assert result["name"] == "storefront"
    assert result["repository_type"] == "MIRRORED"
    assert result["mirror_repository_config"]["connector_id"] == "connector1"
    assert (
        result["mirror_repository_config"]["trigger_schedule"]["schedule_type"]
        == "DEFAULT"
    )
    assert result["freeform_tags"] == {"team": "ops"}


def test_result_renames_misspelled_lifecycle_details(monkeypatch):
    """Normalize the SDK's lifecyle_details spelling across get and list."""
    module_obj = load_repository_info_module(monkeypatch)
    instance = make_repository_info(module_obj, {})
    from_get = instance.serialize_result_resource(
        FakeModel(id="r1", lifecyle_details="working")
    )
    from_list = instance.serialize_result_resource(
        FakeModel(id="r1", lifecycle_details="working")
    )
    assert from_get["lifecycle_details"] == "working"
    assert "lifecyle_details" not in from_get
    assert from_list["lifecycle_details"] == "working"


def test_get_404_returns_empty_and_other_errors_propagate(monkeypatch):
    """Return no repositories for a missing id and raise other OCI errors."""
    module_obj = load_repository_info_module(monkeypatch)
    instance = make_repository_info(
        module_obj, {"repository_id": "r"}, types.SimpleNamespace(get_repository=object())
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


def test_list_scoped_by_project_lifecycle_and_name(monkeypatch):
    """Pass SDK-cased list filters to OCI and keep only exact name matches."""
    module_obj = load_repository_info_module(monkeypatch)
    client = types.SimpleNamespace(list_repositories=object())
    instance = make_repository_info(
        module_obj,
        {
            "project_id": "project1",
            "lifecycle_state": "ACTIVE",
            "name": "storefront",
        },
        client,
    )
    matching = FakeModel(name="storefront", id="r1")
    other = FakeModel(name="storefront-old", id="r2")
    calls = []
    monkeypatch.setattr(
        instance,
        "list_all_resources",
        lambda method, **kwargs: calls.append((method, kwargs)) or [matching, other],
    )
    assert instance.fetch_resources() == [matching]
    assert calls == [
        (
            client.list_repositories,
            {
                "project_id": "project1",
                "lifecycle_state": "ACTIVE",
                "name": "storefront",
            },
        )
    ]


def test_list_scoped_by_compartment(monkeypatch):
    """List repositories across a compartment when no project is given."""
    module_obj = load_repository_info_module(monkeypatch)
    client = types.SimpleNamespace(list_repositories=object())
    instance = make_repository_info(
        module_obj, {"compartment_id": "compartment1"}, client
    )
    repositories = [FakeModel(name="a", id="r1"), FakeModel(name="b", id="r2")]
    calls = []
    monkeypatch.setattr(
        instance,
        "list_all_resources",
        lambda method, **kwargs: calls.append((method, kwargs)) or repositories,
    )
    assert instance.fetch_resources() == repositories
    assert calls == [(client.list_repositories, {"compartment_id": "compartment1"})]


def test_info_result_is_unchanged_and_reports_repositories(monkeypatch):
    """Return serialized repositories under repositories with changed false."""
    module_obj = load_repository_info_module(monkeypatch)
    instance = make_repository_info(module_obj, {})
    monkeypatch.setattr(
        instance,
        "fetch_resources",
        lambda: [FakeModel(id="r", name="storefront", lifecycle_state="ACTIVE")],
    )
    with pytest.raises(ExitJsonCalled) as result:
        instance.execute_info_module()
    assert result.value.payload["changed"] is False
    assert result.value.payload["repositories"] == [
        {"id": "r", "name": "storefront", "lifecycle_state": "ACTIVE"}
    ]
