# -*- coding: utf-8 -*-
# Copyright (c) 2026, Ansible Content Engineering Team
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: oci_devops_repository
short_description: Manage an OCI DevOps repository
description:
  - Create, update, and delete code repositories in an OCI DevOps project.
version_added: "1.2.0"
author:
  - Mike Morency (@mikemorency)
extends_documentation_fragment:
  - ansible.oci.oci_auth_options
  - ansible.oci.oci_wait_options
  - ansible.oci.oci_tags_options
options:
  state:
    description:
      - The desired lifecycle state of the repository.
    type: str
    choices: [present, absent]
    default: present
  repository_id:
    description:
      - The OCID of the repository to manage.
    type: str
  project_id:
    description:
      - The OCID of the DevOps project that contains the repository.
      - Required when creating a repository or when finding a repository by name.
      - This value cannot change after repository creation.
      - The repository inherits its compartment from this project, so the
        compartment cannot be set directly.
    type: str
  name:
    description:
      - The name of the repository. The value is case-sensitive and must be
        unique within the project.
      - Required when creating a repository.
      - When C(repository_id) is omitted, the repository is found by this name
        in C(project_id). Renaming therefore requires C(repository_id), because
        a name lookup would otherwise search for the new name.
    type: str
  description:
    description:
      - The repository description.
      - Omit this option to keep the current description.
    type: str
  default_branch:
    description:
      - The name of the branch that is checked out by default, for example
        C(main).
      - Omit this option to keep the current default branch.
    type: str
  repository_type:
    description:
      - The type of repository to manage.
      - Required when creating a repository. There is deliberately no default,
        because a default would make this module try to convert an existing
        C(mirrored) or C(forked) repository to C(hosted) whenever the option is
        left unset.
      - C(hosted) repositories are created and hosted in OCI DevOps.
      - C(mirrored) repositories mirror an external repository and require
        C(mirror_repository_config).
      - C(forked) repositories are forked from another repository and require
        C(parent_repository_id).
      - Setting this to C(hosted) or C(mirrored) on an existing repository asks
        OCI to convert the repository type. An existing repository cannot be
        converted to C(forked), because OCI accepts C(parent_repository_id)
        only at creation time.
    type: str
    choices: [hosted, mirrored, forked]
  parent_repository_id:
    description:
      - The OCID of the repository this repository was forked from.
      - Required when C(repository_type) is C(forked).
      - This value cannot change after repository creation.
    type: str
  mirror_repository_config:
    description:
      - The configuration used to mirror an external repository.
      - Required when C(repository_type) is C(mirrored).
    type: dict
    suboptions:
      connector_id:
        description:
          - The OCID of the DevOps external connection that holds the
            credentials used to reach the external repository.
        type: str
      repository_url:
        description:
          - The URL of the external repository to mirror.
          - Required when C(repository_type) is C(mirrored).
        type: str
      trigger_schedule:
        description:
          - How often OCI synchronizes the mirror from the external repository.
        type: dict
        suboptions:
          schedule_type:
            description:
              - The synchronization schedule to use.
              - C(none) disables automatic synchronization.
              - C(default) synchronizes every 30 minutes.
              - C(custom) uses the cron expression in C(custom_schedule).
            type: str
            choices: [none, default, custom]
          custom_schedule:
            description:
              - The cron expression used when C(schedule_type) is C(custom).
            type: str
"""

EXAMPLES = r"""
- name: Create a hosted repository
  ansible.oci.oci_devops_repository:
    project_id: ocid1.devopsproject.oc1..example
    name: storefront
    description: Storefront service source
    repository_type: hosted
    default_branch: main

- name: Update the description and tags of a repository
  ansible.oci.oci_devops_repository:
    repository_id: ocid1.devopsrepository.oc1..example
    description: Storefront and checkout service source
    freeform_tags:
      team: platform

- name: Create a mirrored repository that syncs every 30 minutes
  ansible.oci.oci_devops_repository:
    project_id: ocid1.devopsproject.oc1..example
    name: upstream-mirror
    repository_type: mirrored
    mirror_repository_config:
      connector_id: ocid1.devopsconnection.oc1..example
      repository_url: https://github.com/example/upstream.git
      trigger_schedule:
        schedule_type: default

- name: Rename a repository, which requires the repository OCID
  ansible.oci.oci_devops_repository:
    repository_id: ocid1.devopsrepository.oc1..example
    name: storefront-api

- name: Delete a repository found by name within its project
  ansible.oci.oci_devops_repository:
    project_id: ocid1.devopsproject.oc1..example
    name: storefront
    state: absent
"""

RETURN = r"""
resource:
  description: The DevOps repository resource.
  returned: when state is present, except in check mode when a change is predicted
  type: dict
  contains:
    id:
      description: The repository OCID.
      type: str
      returned: always
    name:
      description: The repository name.
      type: str
      returned: always
    project_id:
      description: The OCID of the DevOps project that contains the repository.
      type: str
      returned: always
    project_name:
      description: The name of the DevOps project that contains the repository.
      type: str
      returned: always
    compartment_id:
      description: The OCID of the compartment that contains the repository.
      type: str
      returned: always
    namespace:
      description: The namespace associated with the repository.
      type: str
      returned: always
    parent_repository_id:
      description: The OCID of the repository this repository was forked from.
      type: str
      returned: when the repository is a fork
    description:
      description: The repository description.
      type: str
      returned: when available
    default_branch:
      description: The branch that is checked out by default.
      type: str
      returned: when available
    repository_type:
      description: The repository type.
      type: str
      returned: always
      sample: HOSTED
    ssh_url:
      description: The SSH URL used to clone the repository.
      type: str
      returned: always
    http_url:
      description: The HTTP URL used to clone the repository.
      type: str
      returned: always
    mirror_repository_config:
      description: The mirror configuration of the repository.
      type: dict
      returned: when the repository is a mirror
      contains:
        connector_id:
          description: The OCID of the external connection used to mirror.
          type: str
          returned: when available
        repository_url:
          description: The URL of the mirrored external repository.
          type: str
          returned: when available
        trigger_schedule:
          description: The mirror synchronization schedule.
          type: dict
          returned: when available
          contains:
            schedule_type:
              description: The synchronization schedule type.
              type: str
              returned: always
            custom_schedule:
              description: The cron expression used by a custom schedule.
              type: str
              returned: when the schedule type is CUSTOM
    branch_count:
      description: The number of branches in the repository.
      type: int
      returned: when available
    commit_count:
      description: The number of commits in the repository.
      type: int
      returned: when available
    size_in_bytes:
      description: The size of the repository in bytes.
      type: int
      returned: when available
    trigger_build_events:
      description: The repository events that trigger a build run.
      type: list
      elements: str
      returned: when available
    lifecycle_state:
      description: The repository lifecycle state.
      type: str
      returned: always
      sample: ACTIVE
    lifecycle_details:
      description:
        - A message describing the current lifecycle state in more detail.
        - The OCI SDK spells this field C(lifecyle_details) on the full
          repository model. This module renames it so results use the correct
          spelling consistently.
      type: str
      returned: when available
    time_created:
      description: The date and time when the repository was created.
      type: str
      returned: always
    time_updated:
      description: The date and time when the repository was last updated.
      type: str
      returned: always
    freeform_tags:
      description: Free-form tags applied to the repository.
      type: dict
      returned: always
    defined_tags:
      description: Defined tags applied to the repository.
      type: dict
      returned: always
    system_tags:
      description: System tags applied to the repository.
      type: dict
      returned: when available
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.ansible.oci.plugins.module_utils.oci_common import (
    LIFECYCLE_ACTIVE,
    OCI_AUTH_ARGS,
    OCI_TAG_ARGS,
    OCI_WAIT_ARGS,
    build_model,
    import_oci_sdk,
    merge_mappings,
    normalize_choice_parameters,
    serialize_oci_model,
)
from ansible_collections.ansible.oci.plugins.module_utils.oci_resource import (
    OciResourceBase,
    UpdateFieldSpec,
)

oci = import_oci_sdk()[0]

CREATE_REQUIRED_FIELDS = ("project_id", "name", "repository_type")
WAIT_FOR_REPOSITORY_STATES = (LIFECYCLE_ACTIVE,)

REPOSITORY_TYPE_HOSTED = "HOSTED"
REPOSITORY_TYPE_MIRRORED = "MIRRORED"
REPOSITORY_TYPE_FORKED = "FORKED"

# Module inputs use lowercase snake_case choices (Ansible convention) while OCI
# uses upper-case constants. These are normalized in main() rather than through
# the planner's enum_keys so module.params already holds the OCI spelling by the
# time the update planner compares it against the current repository.
CHOICE_VALUE_MAPS = {
    ("repository_type",): {
        "hosted": REPOSITORY_TYPE_HOSTED,
        "mirrored": REPOSITORY_TYPE_MIRRORED,
        "forked": REPOSITORY_TYPE_FORKED,
    },
    ("mirror_repository_config", "trigger_schedule", "schedule_type"): {
        "none": "NONE",
        "default": "DEFAULT",
        "custom": "CUSTOM",
    },
}

# The full Repository model misspells this field as "lifecyle_details" while
# RepositorySummary spells it correctly, so results would otherwise differ by
# lookup path. Rename it to the correct spelling for a stable result contract.
REPOSITORY_FIELD_ALIASES = {"lifecyle_details": "lifecycle_details"}


def build_mirror_repository_config(mirror_repository_config):
    """Build the OCI mirror configuration model from module input.

    Args:
        mirror_repository_config: The ``mirror_repository_config`` suboption
            mapping, or None when the caller did not supply one.

    Returns:
        An ``oci.devops.models.MirrorRepositoryConfig`` instance, or None when
        ``mirror_repository_config`` is None.
    """
    if mirror_repository_config is None:
        return None
    return build_model(
        dict(
            mirror_repository_config,
            trigger_schedule=build_model(
                mirror_repository_config.get("trigger_schedule"),
                oci.devops.models.TriggerSchedule,
            ),
        ),
        oci.devops.models.MirrorRepositoryConfig,
    )


class OciDevopsRepositoryModule(OciResourceBase):
    """Manage OCI DevOps repositories with shared resource lifecycle helpers."""

    @property
    def client_class(self):
        """Return the OCI DevOps client class.

        Returns:
            The OCI DevopsClient class.
        """
        return oci.devops.DevopsClient

    resource_id_param = "repository_id"
    list_resource_method = "list_repositories"
    name_response_field = "name"
    field_param_aliases = REPOSITORY_FIELD_ALIASES
    # A repository name is unique within its project rather than its
    # compartment, and a repository has no compartment_id option, so the shared
    # compartment scope is replaced with the project scope.
    common_list_filter_params = ("project_id",)
    # list_repositories accepts an exact name filter; pass it so name lookups
    # filter server-side instead of paging the whole project. It is not part
    # of the required lookup scope, so it does not belong in
    # list_filter_params, which is what the scope error messages list.
    name_lookup_filter_params = ("name",)
    create_required_fields = CREATE_REQUIRED_FIELDS
    create_resource_name = "DevOps repository"
    update_method_name = "update_repository"
    update_details_name = "update_repository_details"
    update_wait_states = WAIT_FOR_REPOSITORY_STATES
    update_field_specs = (
        UpdateFieldSpec(param_name="name", is_mutable=True),
        UpdateFieldSpec(
            param_name="project_id",
            is_mutable=False,
            immutable_reason="OCI does not support moving a repository to another project",
        ),
        UpdateFieldSpec(
            param_name="parent_repository_id",
            is_mutable=False,
            immutable_reason="OCI sets the parent repository only when the fork is created",
        ),
        UpdateFieldSpec(param_name="description", is_mutable=True),
        UpdateFieldSpec(param_name="default_branch", is_mutable=True),
        UpdateFieldSpec(param_name="repository_type", is_mutable=True),
        UpdateFieldSpec(
            param_name="mirror_repository_config",
            is_mutable=True,
            compare="subset_dict",
        ),
    )

    def build_update_plan(self, resource):
        """Plan the update, merging the mirror config onto the current one.

        ``mirror_repository_config`` is compared as a subset, so a caller may
        supply only the sub-fields they want to change. OCI replaces the
        nested object wholesale, so sending just those sub-fields would clear
        the rest of the mirror configuration. Merge the supplied fields onto
        the current configuration so the update changes only what the caller
        asked for.

        Args:
            resource: The current repository model.

        Returns:
            The shared update plan with a complete mirror configuration.
        """
        update_plan = super(OciDevopsRepositoryModule, self).build_update_plan(
            resource
        )
        update_model_fields = update_plan["update_model_fields"]
        if update_model_fields.get("mirror_repository_config") is not None:
            current_config = (
                serialize_oci_model(resource).get("mirror_repository_config")
                or {}
            )
            update_model_fields["mirror_repository_config"] = merge_mappings(
                current_config, update_model_fields["mirror_repository_config"]
            )
        return update_plan

    def get_resource_response(self, resource_id):
        """Fetch a repository by OCID with the shared retry wrapper.

        Args:
            resource_id: The repository OCID.

        Returns:
            The OCI response wrapper for the repository.
        """
        return self.call_with_retry(
            self.client.get_repository, repository_id=resource_id
        )

    def hydrate_named_resource(self, resource):
        """Re-fetch a name-resolved repository as the full repository model.

        list_repositories returns a RepositorySummary that omits fields this
        module documents and returns, such as branch_count, commit_count,
        size_in_bytes, and trigger_build_events, and that spells the lifecycle
        detail field differently from the full model. Re-fetching keeps the
        result identical whether the caller passed repository_id or a name.

        Args:
            resource: The repository summary matched by name lookup.

        Returns:
            The full repository model, or the summary when it cannot be
            re-fetched.
        """
        full_resource = self.get_resource_by_id(self.get_resource_ocid(resource))
        return full_resource if full_resource is not None else resource

    def validate_create_request(self):
        """Validate repository-type specific requirements before creating.

        Extends the shared required-field check with the dependent options OCI
        requires for mirrored and forked repositories, so a missing option
        fails with a clear message instead of an opaque OCI 400.

        Raises:
            AnsibleFailJson: Through ``fail_json`` when a required dependent
                option for the requested repository type is missing.
        """
        super(OciDevopsRepositoryModule, self).validate_create_request()
        params = self.module.params
        repository_type = params.get("repository_type")
        if repository_type == REPOSITORY_TYPE_MIRRORED:
            mirror_repository_config = params.get("mirror_repository_config")
            if mirror_repository_config is None:
                self.module.fail_json(
                    msg=(
                        "Creating a mirrored DevOps repository requires "
                        "mirror_repository_config"
                    )
                )
            if mirror_repository_config.get("repository_url") is None:
                self.module.fail_json(
                    msg=(
                        "Creating a mirrored DevOps repository requires "
                        "mirror_repository_config.repository_url"
                    )
                )
        if (
            repository_type == REPOSITORY_TYPE_FORKED
            and params.get("parent_repository_id") is None
        ):
            self.module.fail_json(
                msg=(
                    "Creating a forked DevOps repository requires "
                    "parent_repository_id"
                )
            )

    def create_resource(self):
        """Create a repository and wait for its active state.

        Returns:
            The created repository model after the configured wait.
        """
        params = self.module.params
        details = build_model(
            {
                "project_id": params.get("project_id"),
                "name": params.get("name"),
                "description": params.get("description"),
                "default_branch": params.get("default_branch"),
                "repository_type": params.get("repository_type"),
                "parent_repository_id": params.get("parent_repository_id"),
                "mirror_repository_config": build_mirror_repository_config(
                    params.get("mirror_repository_config")
                ),
                "freeform_tags": params.get("freeform_tags"),
                "defined_tags": params.get("defined_tags"),
            },
            oci.devops.models.CreateRepositoryDetails,
        )
        response = self.call_with_retry(
            self.client.create_repository, create_repository_details=details
        )
        return self.get_mutation_result(
            response.data,
            getattr(response.data, "id", None),
            WAIT_FOR_REPOSITORY_STATES,
        )

    def build_update_details(self, update_model_fields):
        """Build the OCI repository update model from planned field changes.

        Args:
            update_model_fields: The changed fields selected by the planner.

        Returns:
            The OCI UpdateRepositoryDetails model.
        """
        update_model_fields = dict(update_model_fields)
        mirror_repository_config = update_model_fields.get("mirror_repository_config")
        if mirror_repository_config is not None:
            update_model_fields["mirror_repository_config"] = (
                build_mirror_repository_config(mirror_repository_config)
            )
        return build_model(
            update_model_fields, oci.devops.models.UpdateRepositoryDetails
        )

    def delete_resource(self, resource):
        """Delete a repository through the shared delete and wait helper.

        Args:
            resource: The repository model to delete.

        Returns:
            The final repository model, or None when the repository is gone.
        """
        return self.delete_resource_and_wait(
            resource,
            self.client.delete_repository,
            repository_id=resource.id,
        )


def main():
    """Build the Ansible argument spec and run the repository resource module."""
    argument_spec = dict(
        OCI_AUTH_ARGS,
        **OCI_WAIT_ARGS,
        **OCI_TAG_ARGS,
        state=dict(type="str", choices=["present", "absent"], default="present"),
        repository_id=dict(type="str"),
        project_id=dict(type="str"),
        name=dict(type="str"),
        description=dict(type="str"),
        default_branch=dict(type="str"),
        repository_type=dict(
            type="str",
            choices=list(CHOICE_VALUE_MAPS[("repository_type",)]),
        ),
        parent_repository_id=dict(type="str"),
        mirror_repository_config=dict(
            type="dict",
            options=dict(
                connector_id=dict(type="str"),
                repository_url=dict(type="str"),
                trigger_schedule=dict(
                    type="dict",
                    options=dict(
                        schedule_type=dict(
                            type="str",
                            choices=list(
                                CHOICE_VALUE_MAPS[
                                    (
                                        "mirror_repository_config",
                                        "trigger_schedule",
                                        "schedule_type",
                                    )
                                ]
                            ),
                        ),
                        custom_schedule=dict(type="str"),
                    ),
                ),
            ),
        ),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    normalize_choice_parameters(module, CHOICE_VALUE_MAPS)
    OciDevopsRepositoryModule(module).execute_resource_module()


if __name__ == "__main__":
    main()
