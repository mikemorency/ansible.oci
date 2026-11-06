# -*- coding: utf-8 -*-
# Copyright (c) 2026, Ansible Content Engineering Team
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: oci_devops_repository_info
short_description: Retrieve OCI DevOps repository information
description:
  - Retrieve one or more code repositories from OCI DevOps.
version_added: "1.2.0"
author:
  - Mike Morency (@mikemorency)
extends_documentation_fragment:
  - ansible.oci.oci_auth_options
  - ansible.oci.oci_info_filter_options
options:
  repository_id:
    description:
      - The OCID of the repository to retrieve.
    type: str
  project_id:
    description:
      - The OCID of the DevOps project from which to list repositories.
      - Required when neither C(repository_id) nor C(compartment_id) is set.
    type: str
  compartment_id:
    description:
      - The OCID of the compartment from which to list repositories.
      - Required when neither C(repository_id) nor C(project_id) is set.
    type: str
  name:
    description:
      - Filter returned repositories by exact repository name. The value is
        case-sensitive.
    type: str
  lifecycle_state:
    description:
      - Filter repositories by lifecycle state.
    type: str
    choices: [creating, active, deleting, deleted, failed]
"""

EXAMPLES = r"""
- name: List active repositories in a project
  ansible.oci.oci_devops_repository_info:
    project_id: ocid1.devopsproject.oc1..example
    lifecycle_state: active

- name: List every repository in a compartment
  ansible.oci.oci_devops_repository_info:
    compartment_id: ocid1.compartment.oc1..example

- name: Find a repository by exact name within a project
  ansible.oci.oci_devops_repository_info:
    project_id: ocid1.devopsproject.oc1..example
    name: storefront

- name: Get a repository by OCID
  ansible.oci.oci_devops_repository_info:
    repository_id: ocid1.devopsrepository.oc1..example
"""

RETURN = r"""
repositories:
  description: Repositories that matched the query.
  returned: always
  type: list
  elements: dict
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
      returned: when a single repository is retrieved by repository_id
    commit_count:
      description: The number of commits in the repository.
      type: int
      returned: when a single repository is retrieved by repository_id
    size_in_bytes:
      description: The size of the repository in bytes.
      type: int
      returned: when a single repository is retrieved by repository_id
    trigger_build_events:
      description: The repository events that trigger a build run.
      type: list
      elements: str
      returned: when a single repository is retrieved by repository_id
    lifecycle_state:
      description: The repository lifecycle state.
      type: str
      returned: always
    lifecycle_details:
      description:
        - A message describing the current lifecycle state in more detail.
        - The OCI SDK spells this field C(lifecyle_details) on the full
          repository model returned for C(repository_id). This module renames
          it so results use the correct spelling consistently.
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
    OCI_AUTH_ARGS,
    import_oci_sdk,
    normalize_choice_parameters,
)
from ansible_collections.ansible.oci.plugins.module_utils.oci_info import OciInfoBase

oci = import_oci_sdk()[0]


CHOICE_VALUE_MAPS = {
    ("lifecycle_state",): {
        "creating": "CREATING",
        "active": "ACTIVE",
        "deleting": "DELETING",
        "deleted": "DELETED",
        "failed": "FAILED",
    },
}

# The full Repository model misspells this field as "lifecyle_details" while
# RepositorySummary spells it correctly, so a get by repository_id and a list
# would otherwise disagree. Rename it to the correct spelling for both paths.
REPOSITORY_FIELD_ALIASES = {"lifecyle_details": "lifecycle_details"}


class OciDevopsRepositoryInfoModule(OciInfoBase):
    """Retrieve OCI DevOps repositories with shared get and list helpers."""

    @property
    def client_class(self):
        """Return the OCI DevOps client class.

        Returns:
            The OCI DevopsClient class.
        """
        return oci.devops.DevopsClient

    results_key = "repositories"
    resource_id_param = "repository_id"
    resource_get_method = "get_repository"
    list_resource_method = "list_repositories"
    name_response_field = "name"
    field_param_aliases = REPOSITORY_FIELD_ALIASES
    list_filter_params = (
        "compartment_id",
        "project_id",
        "lifecycle_state",
        "name",
    )


def main():
    """Build the Ansible argument spec and run the repository info module."""
    argument_spec = dict(
        OCI_AUTH_ARGS,
        repository_id=dict(type="str"),
        project_id=dict(type="str"),
        compartment_id=dict(type="str"),
        name=dict(type="str"),
        lifecycle_state=dict(
            type="str",
            choices=list(CHOICE_VALUE_MAPS[("lifecycle_state",)]),
        ),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[["compartment_id", "project_id", "repository_id"]],
    )
    normalize_choice_parameters(module, CHOICE_VALUE_MAPS)
    OciDevopsRepositoryInfoModule(module).execute_info_module()


if __name__ == "__main__":
    main()
