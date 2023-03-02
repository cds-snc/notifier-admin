from flask import current_app
from simple_salesforce import Salesforce

from app.models.user import User

from .salesforce_auth import get_session
from .salesforce_utils import (
    get_name_parts,
    parse_result,
    query_one,
    query_param_sanitize,
)


def create(user: User, account_id: str | None = None, session: Salesforce = None) -> bool:
    """Create a Salesforce Contact from the given Notify User

    Args:
        user (User): Notify User that has just been activated.
        account_id (str | None, optional): ID of the Account to associate the Contact with.
        session (Salesforce | None, optional): Existing Salesforce session. Defaults to None.

    Returns:
        bool: Was the Contact created?
    """
    is_created = False
    try:
        session = session if session else get_session()
        name_parts = get_name_parts(user.name)
        result = session.Contact.create(
            {
                "FirstName": name_parts["first"] if name_parts["first"] else user.name,
                "LastName": name_parts["last"] if name_parts["last"] else "",
                "Email": user.email_address,
                "Phone": user.mobile_number,
                "AccountId": account_id,
            }
        )
        is_created = parse_result(result, f"Salesforce Contact create for '{user.email_address}'")

    except Exception as ex:
        current_app.logger.error(f"Salesforce Contact create failed: {ex}")
    return is_created


def update_account_id(user: User, account_id: str, session: Salesforce = None) -> bool:
    """Update the Account ID of a Contact.  If the Contact does not
    exist, it is created.

    Args:
        email (str): Email address of the contact to update
        account_id (str): ID of the Salesforce Account

    Returns:
        bool: Was the Contact updated?
    """
    is_updated = False
    try:
        session = session if session else get_session()
        contact = get_contact_by_email(user.email_address, session)

        # Existing contact, update the AccountID
        if contact:
            result = session.Contact.update(contact.get("Id"), {"AccountId": account_id})
            is_updated = parse_result(result, f"Salesforce Contact update '{user.email_address}' with account ID '{account_id}'")
        # Create the contact.  This handles Notify users that were created before Salesforce was added.
        else:
            is_updated = create(user, account_id, session)

    except Exception as ex:
        current_app.logger.error(f"Salesforce Contact updated failed: {ex}")
    return is_updated


def get_contact_by_email(email: str, session: Salesforce) -> dict[str, str] | None:
    """Retrieve a Salesforce Contact by their email address.  If
    they can't be found, `None` is returned.

    Args:
        email (str): Email of the Salesforce Contact to retrieve
        session (Salesforce | None, optional): Existing Salesforce session. Defaults to None.

    Returns:
        dict[str, str] | None: Salesforce Contact details no None if can't be found
    """
    query = f"SELECT Id, FirstName, LastName, AccountId FROM Contact WHERE Email = '{query_param_sanitize(email)}' LIMIT 1"
    return query_one(query, session)