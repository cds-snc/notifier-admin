from itertools import chain

from flask_babel import lazy_gettext as _l

roles = {
    "send_messages": ["send_texts", "send_emails", "send_letters"],
    "manage_templates": ["manage_templates"],
    "manage_service": ["manage_users", "manage_settings"],
    "manage_api_keys": ["manage_api_keys"],
    "view_activity": ["view_activity"],
}

# same dict as above, but flipped round
roles_by_permission = {
    permission: next(role for role, permissions in roles.items() if permission in permissions)
    for permission in chain(*list(roles.values()))
}

all_permissions = set(roles_by_permission.values())

permissions = (
    ("view_activity", _l("View dashboard statistics, reports and usage data")),
    ("manage_templates", _l("Create and edit message templates")),
    ("send_messages", _l("Send messages")),
    ("manage_service", _l("Manage settings and team members")),
    ("manage_api_keys", _l("Manage API integration")),
)


def translate_permissions_from_db_to_admin_roles(permissions):
    """
    Given a list of database permissions, return a set of roles

    look them up in roles_by_permission, falling back to just passing through from the api if they aren't in the dict
    """
    return {roles_by_permission.get(permission, permission) for permission in permissions}


def translate_permissions_from_admin_roles_to_db(permissions):
    """
    Given a list of admin roles (ie: checkboxes on a permissions edit page for example), return a set of db permissions

    Looks them up in the roles dict, falling back to just passing through if they're not recognised.
    """
    return set(chain.from_iterable(roles.get(permission, [permission]) for permission in permissions))
