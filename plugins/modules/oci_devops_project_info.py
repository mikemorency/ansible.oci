# -*- coding: utf-8 -*-
# Copyright (c) 2026, Ansible Content Engineering Team
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: oci_devops_project_info
short_description: Retrieve OCI DevOps project information
description:
  - Retrieve one or more OCI DevOps projects.
version_added: "1.2.0"
author:
  - Mike Morency (@mikemorency)
extends_documentation_fragment:
  - ansible.oci.oci_auth_options
  - ansible.oci.oci_info_filter_options
options:
  project_id:
    description:
      - The OCID of the project to retrieve.
    type: str
  compartment_id:
    description:
      - The OCID of the compartment from which to list projects.
      - Required when C(project_id) is not set.
    type: str
  name:
    description:
      - Filter returned projects by exact project name. The value is case-sensitive.
    type: str
  lifecycle_state:
    description:
      - Filter projects by lifecycle state.
    type: str
    choices: [creating, updating, active, deleting, deleted, failed, needs_attention]
"""

EXAMPLES = r"""
- name: List active projects in a compartment
  ansible.oci.oci_devops_project_info:
    compartment_id: ocid1.compartment.oc1..example
    lifecycle_state: active

- name: Find a project by exact name
  ansible.oci.oci_devops_project_info:
    compartment_id: ocid1.compartment.oc1..example
    name: example-project

- name: Get a project by OCID
  ansible.oci.oci_devops_project_info:
    project_id: ocid1.devopsproject.oc1..example
"""

RETURN = r"""
projects:
  description: Projects that matched the query.
  returned: always
  type: list
  elements: dict
  contains:
    id:
      description: The project OCID.
      type: str
      returned: always
    name:
      description: The project name.
      type: str
      returned: always
    compartment_id:
      description: The OCID of the compartment that contains the project.
      type: str
      returned: always
    description:
      description: The project description.
      type: str
      returned: when available
    namespace:
      description: The namespace associated with the project.
      type: str
      returned: always
    notification_config:
      description: The notification configuration of the project.
      type: dict
      returned: always
      contains:
        topic_id:
          description: The OCID of the topic that receives project events.
          type: str
          returned: always
    lifecycle_state:
      description: The project lifecycle state.
      type: str
      returned: always
    lifecycle_details:
      description: A message describing the current lifecycle state in more detail.
      type: str
      returned: when available
    time_created:
      description: The date and time when the project was created.
      type: str
      returned: always
    time_updated:
      description: The date and time when the project was last updated.
      type: str
      returned: always
    freeform_tags:
      description: Free-form tags applied to the project.
      type: dict
      returned: always
    defined_tags:
      description: Defined tags applied to the project.
      type: dict
      returned: always
    system_tags:
      description: System tags applied to the project.
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
        "updating": "UPDATING",
        "active": "ACTIVE",
        "deleting": "DELETING",
        "deleted": "DELETED",
        "failed": "FAILED",
        "needs_attention": "NEEDS_ATTENTION",
    },
}


class OciDevopsProjectInfoModule(OciInfoBase):
    """Retrieve OCI DevOps projects with shared get and list helpers."""

    @property
    def client_class(self):
        """Return the OCI DevOps client class.

        Returns:
            The OCI DevopsClient class.
        """
        return oci.devops.DevopsClient

    results_key = "projects"
    resource_id_param = "project_id"
    resource_get_method = "get_project"
    list_resource_method = "list_projects"
    name_response_field = "name"
    list_filter_params = ("compartment_id", "lifecycle_state", "name")


def main():
    """Build the Ansible argument spec and run the project info module."""
    argument_spec = dict(
        OCI_AUTH_ARGS,
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
        required_one_of=[["compartment_id", "project_id"]],
    )
    normalize_choice_parameters(module, CHOICE_VALUE_MAPS)
    OciDevopsProjectInfoModule(module).execute_info_module()


if __name__ == "__main__":
    main()
