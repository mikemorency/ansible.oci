# -*- coding: utf-8 -*-
# Copyright (c) 2026, Ansible Content Engineering Team
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: oci_devops_project
short_description: Manage an OCI DevOps project
description:
  - Create, update, and delete OCI DevOps projects.
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
      - The desired lifecycle state of the project.
    type: str
    choices: [present, absent]
    default: present
  project_id:
    description:
      - The OCID of the project to manage.
    type: str
  compartment_id:
    description:
      - The OCID of the compartment that contains the project.
      - Required when creating a project or when finding a project by name.
      - This value cannot change after project creation. Moving a project to
        another compartment is not supported by this module.
    type: str
  name:
    description:
      - The name of the project. The value is case-sensitive.
      - Required when creating a project.
      - This value cannot change after project creation.
      - When C(project_id) is omitted, the project is found by this name in
        C(compartment_id).
    type: str
  description:
    description:
      - The project description.
      - Omit this option to keep the current description.
    type: str
  notification_config:
    description:
      - The notification configuration that DevOps uses to report project events.
      - Required when creating a project, because OCI rejects a project that has
        no notification topic.
    type: dict
    suboptions:
      topic_id:
        description:
          - The OCID of the OCI Notifications topic that receives project events.
        type: str
        required: true
"""

EXAMPLES = r"""
- name: Create a DevOps project
  ansible.oci.oci_devops_project:
    compartment_id: ocid1.compartment.oc1..example
    name: example-project
    description: Build and deploy pipelines for the storefront
    notification_config:
      topic_id: ocid1.onstopic.oc1..example

- name: Update the description and tags of a project
  ansible.oci.oci_devops_project:
    project_id: ocid1.devopsproject.oc1..example
    description: Build and deploy pipelines for the storefront and checkout
    freeform_tags:
      team: platform

- name: Point a project at a different notification topic by name lookup
  ansible.oci.oci_devops_project:
    compartment_id: ocid1.compartment.oc1..example
    name: example-project
    notification_config:
      topic_id: ocid1.onstopic.oc1..other

- name: Delete a DevOps project
  ansible.oci.oci_devops_project:
    project_id: ocid1.devopsproject.oc1..example
    state: absent
"""

RETURN = r"""
resource:
  description: The DevOps project resource.
  returned: when state is present, except in check mode when a change is predicted
  type: dict
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
      sample: ACTIVE
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
    LIFECYCLE_ACTIVE,
    OCI_AUTH_ARGS,
    OCI_TAG_ARGS,
    OCI_WAIT_ARGS,
    build_model,
    import_oci_sdk,
)
from ansible_collections.ansible.oci.plugins.module_utils.oci_resource import (
    OciResourceBase,
    UpdateFieldSpec,
)

oci = import_oci_sdk()[0]

CREATE_REQUIRED_FIELDS = ("compartment_id", "name", "notification_config")
WAIT_FOR_PROJECT_STATES = (LIFECYCLE_ACTIVE,)


class OciDevopsProjectModule(OciResourceBase):
    """Manage OCI DevOps projects with shared resource lifecycle helpers."""

    @property
    def client_class(self):
        """Return the OCI DevOps client class.

        Returns:
            The OCI DevopsClient class.
        """
        return oci.devops.DevopsClient

    resource_id_param = "project_id"
    list_resource_method = "list_projects"
    name_response_field = "name"
    # list_projects accepts an exact name filter; pass it so name lookups
    # filter server-side instead of paging the whole compartment.
    list_filter_params = ("name",)
    create_required_fields = CREATE_REQUIRED_FIELDS
    create_resource_name = "DevOps project"
    update_method_name = "update_project"
    update_details_name = "update_project_details"
    update_wait_states = WAIT_FOR_PROJECT_STATES
    update_field_specs = (
        UpdateFieldSpec(param_name="name", is_mutable=False),
        UpdateFieldSpec(
            param_name="compartment_id",
            is_mutable=False,
            immutable_reason="OCI only moves a project between compartments through a separate operation",
        ),
        UpdateFieldSpec(param_name="description", is_mutable=True),
        UpdateFieldSpec(
            param_name="notification_config",
            is_mutable=True,
            compare="subset_dict",
        ),
    )

    def get_resource_response(self, resource_id):
        """Fetch a project by OCID with the shared retry wrapper.

        Args:
            resource_id: The project OCID.

        Returns:
            The OCI response wrapper for the project.
        """
        return self.call_with_retry(self.client.get_project, project_id=resource_id)

    def create_resource(self):
        """Create a project and wait for its active state.

        Returns:
            The created project model after the configured wait.
        """
        params = self.module.params
        details = build_model(
            {
                "compartment_id": params.get("compartment_id"),
                "name": params.get("name"),
                "description": params.get("description"),
                "notification_config": build_model(
                    params.get("notification_config"),
                    oci.devops.models.NotificationConfig,
                ),
                "freeform_tags": params.get("freeform_tags"),
                "defined_tags": params.get("defined_tags"),
            },
            oci.devops.models.CreateProjectDetails,
        )
        response = self.call_with_retry(
            self.client.create_project, create_project_details=details
        )
        return self.get_mutation_result(
            response.data,
            getattr(response.data, "id", None),
            WAIT_FOR_PROJECT_STATES,
        )

    def build_update_details(self, update_model_fields):
        """Build the OCI project update model from planned field changes.

        Args:
            update_model_fields: The changed fields selected by the planner.

        Returns:
            The OCI UpdateProjectDetails model.
        """
        update_model_fields = dict(update_model_fields)
        notification_config = update_model_fields.get("notification_config")
        if notification_config is not None:
            update_model_fields["notification_config"] = build_model(
                notification_config, oci.devops.models.NotificationConfig
            )
        return build_model(update_model_fields, oci.devops.models.UpdateProjectDetails)

    def delete_resource(self, resource):
        """Delete a project through the shared delete and wait helper.

        Args:
            resource: The project model to delete.

        Returns:
            The final project model, or None when the project is gone.
        """
        return self.delete_resource_and_wait(
            resource,
            self.client.delete_project,
            project_id=resource.id,
        )


def main():
    """Build the Ansible argument spec and run the project resource module."""
    argument_spec = dict(
        OCI_AUTH_ARGS,
        **OCI_WAIT_ARGS,
        **OCI_TAG_ARGS,
        state=dict(type="str", choices=["present", "absent"], default="present"),
        project_id=dict(type="str"),
        compartment_id=dict(type="str"),
        name=dict(type="str"),
        description=dict(type="str"),
        notification_config=dict(
            type="dict",
            options=dict(
                topic_id=dict(type="str", required=True),
            ),
        ),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    OciDevopsProjectModule(module).execute_resource_module()


if __name__ == "__main__":
    main()
