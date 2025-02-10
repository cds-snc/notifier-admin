import os
from functools import partial
from unittest.mock import PropertyMock, call
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import pytest
from bs4 import BeautifulSoup
from flask import Flask, url_for
from freezegun import freeze_time
from pytest_mock import MockerFixture

import app
from app.models.service import Service
from app.utils import email_safe
from tests import (
    organisation_json,
    sample_uuid,
    service_json,
    validate_route_permission,
)
from tests.conftest import (
    ORGANISATION_ID,
    SERVICE_ONE_ID,
    TEMPLATE_ONE_ID,
    ClientRequest,
    create_active_user_no_api_key_permission,
    create_active_user_no_settings_permission,
    create_active_user_with_permissions,
    create_letter_contact_block,
    create_multiple_email_reply_to_addresses,
    create_multiple_letter_contact_blocks,
    create_multiple_sms_senders,
    create_platform_admin_user,
    create_reply_to_email_address,
    create_sample_invite,
    create_sms_sender,
    mock_get_service_organisation,
    normalize_spaces,
    set_config,
)

FAKE_TEMPLATE_ID = uuid4()


@pytest.fixture
def mock_get_service_settings_page_common(
    mock_get_all_letter_branding,
    mock_get_inbound_number_for_service,
    mock_get_free_sms_fragment_limit,
    mock_get_service_data_retention,
):
    return


@pytest.mark.parametrize(
    "user, sending_domain, expected_rows",
    [
        (
            create_active_user_with_permissions(),
            None,
            [
                "Label Value Action",
                "Service name Test Service Change",
                "Sending email address name test.service@{sending_domain} Change",
                "Sign-in method Text message code Change",
                "API rate limit per minute 100 calls",
                "Label Value Action",
                "Send emails On Change",
                "Reply-to addresses Not set Manage",
                "Email branding English Government of Canada signature Change",
                "Send files by email Off (API-only) Change",
                "Daily maximum 1,000 emails",
                "Annual maximum(April 1 to March 31) 20,000,000 emails",
                "Label Value Action",
                "Send text messages On Change",
                "Start text messages with service name On Change",
                "Send international text messages Off Change",
                "Daily maximum 1,000 text messages",
                "Annual maximum(April 1 to March 31) 100,000 text messages",
            ],
        ),
        (
            create_platform_admin_user(),
            "test.example.com",
            [
                "Label Value Action",
                "Service name Test Service Change",
                "Sending email address name test.service@{sending_domain} Change",
                "Sign-in method Text message code Change",
                "API rate limit per minute 100 calls",
                "Label Value Action",
                "Send emails On Change",
                "Reply-to addresses Not set Manage",
                "Email branding English Government of Canada signature Change",
                "Send files by email Off (API-only) Change",
                "Daily maximum 1,000 emails",
                "Annual maximum(April 1 to March 31) 20,000,000 emails",
                "Label Value Action",
                "Send text messages On Change",
                "Start text messages with service name On Change",
                "Send international text messages Off Change",
                "Daily maximum 1,000 text messages",
                "Annual maximum(April 1 to March 31) 100,000 text messages",
                "Label Value Action",
                "Live On Change",
                "Count in list of live services Yes Change",
                "Organisation Test Organisation Government of Canada Change",
                "Daily email limit 1,000 Change",
                "Daily text message limit 1,000 Change",
                "Annual email limit 20,000,000 Change",
                "Annual text message limit 100,000 Change",
                "API rate limit per minute 100",
                "Text message senders GOVUK Manage",
                "Receive text messages Off Change",
                "Free text messages per fiscal year 250,000 Change",
                "Email branding English Government of Canada signature Change",
                "Data retention email Change",
                "Receive inbound SMS Off Change",
                "Email authentication Off Change",
            ],
        ),
    ],
)
def test_should_show_overview_inc_sms_daily_limit(
    client,
    mocker,
    api_user_active,
    fake_uuid,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    mock_get_service_organisation,
    single_sms_sender,
    user,
    sending_domain,
    expected_rows,
    mock_get_service_settings_page_common,
    app_,
):
    # TODO FF_ANNUAL_LIMIT removal
    with set_config(app_, "FF_ANNUAL_LIMIT", True):
        service_one = service_json(
            SERVICE_ONE_ID,
            users=[api_user_active["id"]],
            permissions=["sms", "email"],
            organisation_id=ORGANISATION_ID,
            restricted=False,
            sending_domain=sending_domain,
        )
        mocker.patch("app.service_api_client.get_service", return_value={"data": service_one})

        client.login(user, mocker, service_one)
        response = client.get(url_for("main.service_settings", service_id=SERVICE_ONE_ID))
        assert response.status_code == 200
        page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
        assert page.find("h1").text == "Settings"
        rows = page.select("tr")
        for index, row in enumerate(expected_rows):
            formatted_row = row.format(sending_domain=sending_domain or app_.config["SENDING_DOMAIN"])
            visible = rows[index]
            sr_only = visible.find("span", "sr-only")
            if sr_only:
                sr_only.extract()
                assert " ".join(visible.text.split()).startswith(" ".join(sr_only.text.split()))
            assert formatted_row == " ".join(rows[index].text.split())
        app.service_api_client.get_service.assert_called_with(SERVICE_ONE_ID)


def test_no_go_live_link_for_service_without_organisation(
    client_request,
    mocker,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    single_sms_sender,
    platform_admin_user,
    mock_get_service_settings_page_common,
    app_,
):
    mocker.patch("app.organisations_client.get_service_organisation", return_value=None)
    client_request.login(platform_admin_user)
    page = client_request.get("main.service_settings", service_id=SERVICE_ONE_ID)

    live_row_text = normalize_spaces(page.css.select("tr:contains('No (organisation must be set first)')")[0].text)
    org_row_text = normalize_spaces(page.css.select("tr > td > span:-soup-contains('Not set')")[0].text)
    default_org = normalize_spaces(
        page.css.select("tr:-soup-contains('Organisation') > td > div:-soup-contains('Government of Canada')")[0].text
    )

    assert page.find("h1").text == "Settings"

    assert live_row_text == ("Live No (organisation must be set first)")
    assert org_row_text == ("Not set")
    assert default_org == ("Government of Canada")


def test_organisation_name_links_to_org_dashboard(
    client_request,
    platform_admin_user,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    single_sms_sender,
    mock_get_service_settings_page_common,
    mocker,
    mock_get_service_organisation,
    service_one,
    app_,
):
    service_one = service_json(SERVICE_ONE_ID, permissions=["sms", "email"], organisation_id=ORGANISATION_ID)
    mocker.patch("app.service_api_client.get_service", return_value={"data": service_one})

    client_request.login(platform_admin_user, service_one)
    response = client_request.get("main.service_settings", service_id=SERVICE_ONE_ID)

    org_row = response.css.select("tr:-soup-contains('Organisation')")[0]

    assert org_row.find("a")["href"] == url_for("main.organisation_dashboard", org_id=ORGANISATION_ID)
    assert normalize_spaces(org_row.find("a").text) == "Test Organisation"


@pytest.mark.parametrize(
    "permissions, expected_rows",
    [
        (
            ["email", "sms", "inbound_sms", "international_sms"],
            [
                "Service name service one Change",
                "Sending email address name test.service@{sending_domain} Change",
                "Sign-in method Text message code Change",
                "API rate limit per minute 100 calls",
                "Label Value Action",
                "Send emails On Change",
                "Reply-to addresses test@example.com Manage",
                "Email branding Your branding (Organisation name) Change",
                "Send files by email Off (API-only) Change",
                "Daily maximum 1,000 emails",
                "Annual maximum(April 1 to March 31) 20,000,000 emails",
                "Label Value Action",
                "Send text messages On Change",
                "Start text messages with service name On Change",
                "Send international text messages On Change",
                "Daily maximum 1,000 text messages",
                "Annual maximum(April 1 to March 31) 100,000 text messages",
            ],
        ),
        (
            ["email", "sms", "email_auth"],
            [
                "Service name service one Change",
                "Sending email address name test.service@{sending_domain} Change",
                "Sign-in method Email code or text message code Change",
                "API rate limit per minute 100 calls",
                "Label Value Action",
                "Send emails On Change",
                "Reply-to addresses test@example.com Manage",
                "Email branding Your branding (Organisation name) Change",
                "Send files by email Off (API-only) Change",
                "Daily maximum 1,000 emails",
                "Annual maximum(April 1 to March 31) 20,000,000 emails",
                "Label Value Action",
                "Send text messages On Change",
                "Start text messages with service name On Change",
                "Send international text messages Off Change",
                "Daily maximum 1,000 text messages",
                "Annual maximum(April 1 to March 31) 100,000 text messages",
            ],
        ),
    ],
)
def test_should_show_overview_for_service_with_more_things_set_inc_sms_daily_limit(
    client,
    active_user_with_permissions,
    mocker,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    single_sms_sender,
    mock_get_service_organisation,
    mock_get_email_branding,
    mock_get_service_settings_page_common,
    permissions,
    expected_rows,
    app_,
):
    # TODO FF_ANNUAL_LIMIT removal
    with set_config(app_, "FF_ANNUAL_LIMIT", True):
        client.login(active_user_with_permissions, mocker, service_one)
        service_one["permissions"] = permissions
        service_one["email_branding"] = uuid4()
        response = client.get(url_for("main.service_settings", service_id=service_one["id"]))
        page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
        rows = page.find_all("tr")
        for index, row in enumerate(expected_rows):
            formatted_row = row.format(sending_domain=os.environ.get("SENDING_DOMAIN", "notification.alpha.canada.ca"))
            visible = rows[index + 1]
            sr_only = visible.find("span", "sr-only")
            if sr_only:
                sr_only.extract()
                assert " ".join(visible.text.split()).startswith(" ".join(sr_only.text.split()))
            assert formatted_row == " ".join(visible.text.split())


def test_if_cant_send_letters_then_cant_see_letter_contact_block(
    client_request,
    service_one,
    single_reply_to_email_address,
    no_letter_contact_blocks,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
):
    response = client_request.get("main.service_settings", service_id=service_one["id"])
    assert "Letter contact block" not in response


@pytest.mark.skip(reason="feature not in use")
def test_letter_contact_block_shows_none_if_not_set(
    client_request,
    service_one,
    single_reply_to_email_address,
    no_letter_contact_blocks,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
):
    service_one["permissions"] = ["letter"]
    page = client_request.get(
        "main.service_settings",
        service_id=SERVICE_ONE_ID,
    )

    div = page.find_all("tr")[9].find_all("td")[1].div
    assert div.text.strip() == "Not set"
    assert "default" in div.attrs["class"][0]


@pytest.mark.skip(reason="feature not in use")
def test_escapes_letter_contact_block(
    client_request,
    service_one,
    mocker,
    single_reply_to_email_address,
    single_sms_sender,
    mock_get_service_organisation,
    injected_letter_contact_block,
    mock_get_service_settings_page_common,
):
    service_one["permissions"] = ["letter"]
    page = client_request.get(
        "main.service_settings",
        service_id=SERVICE_ONE_ID,
    )

    div = str(page.find_all("tr")[9].find_all("td")[1].div)
    assert "foo<br/>bar" in div
    assert "<script>" not in div


def test_should_show_service_name(
    client_request,
):
    page = client_request.get("main.service_name_change", service_id=SERVICE_ONE_ID)
    assert page.find("h1").text == "Change your service name"
    assert page.find("input", attrs={"type": "text"})["value"] == "service one"
    assert (
        normalize_spaces(page.select_one("div[class~='form-group'] span[id='name-hint']").text)
        == "Use a name that recipients will recognize. Maximum 255 characters."
    )
    assert normalize_spaces(page.select_one("main ul").text) == ("as your email sender name. at the start of every text message.")
    app.service_api_client.get_service.assert_called_with(SERVICE_ONE_ID)


def test_should_show_service_name_with_no_prefixing(
    client_request,
    service_one,
):
    service_one["prefix_sms"] = False
    page = client_request.get("main.service_name_change", service_id=SERVICE_ONE_ID)
    assert page.find("h1").text == "Change your service name"
    assert (
        normalize_spaces(page.select_one("div[class~='form-group'] span[id='name-hint']").text)
        == "Use a name that recipients will recognize. Maximum 255 characters."
    )


def test_should_redirect_after_change_service_name(
    client_request,
    mock_update_service,
    mock_service_name_is_unique,
):
    client_request.post(
        "main.service_name_change",
        service_id=SERVICE_ONE_ID,
        _data={"name": "new name"},
        _expected_status=302,
        _expected_redirect=url_for(
            "main.service_name_change_confirm",
            service_id=SERVICE_ONE_ID,
        ),
    )

    assert mock_service_name_is_unique.called is True


@pytest.mark.parametrize(
    "user, expected_text, expected_link",
    [
        (
            create_active_user_with_permissions(),
            "To send notifications to more people, request to go live.",
            True,
        ),
        (
            create_active_user_no_settings_permission(),
            "Your service manager can ask to have these restrictions removed.",
            False,
        ),
    ],
)
def test_show_restricted_service(
    client_request,
    fake_uuid,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
    user,
    expected_text,
    expected_link,
):
    client_request.login(user)
    page = client_request.get(
        "main.service_settings",
        service_id=SERVICE_ONE_ID,
    )

    assert page.find("h1").text == "Settings"
    assert page.find_all("h2")[1].text == "Your service is in trial mode"

    assert expected_text in [normalize_spaces(p.text) for p in page.select("main p")]

    if expected_link:
        request_to_live_link = page.select_one("[data-testid='golivebtn']")
        assert request_to_live_link.text.strip() == "Request to go live"
        assert request_to_live_link["href"] == url_for(".request_to_go_live", service_id=SERVICE_ONE_ID)
    else:
        assert url_for(".request_to_go_live", service_id=SERVICE_ONE_ID) not in page


@freeze_time("2017-04-01 11:09:00.061258")
@pytest.mark.parametrize(
    "current_limit, expected_limit, current_sms_limit, expected_sms_limit",
    [
        (42, 10_000, 33, 1000),
        # Maps to DEFAULT_SERVICE_LIMIT and DEFAULT_LIVE_SERVICE_LIMIT in config
        (50, 10_000, 50, 1000),
        (50_000, 10_000, 3000, 1000),
    ],
)
def test_switch_service_to_live(
    client_request,
    platform_admin_user,
    mock_update_service,
    service_one,
    current_limit,
    expected_limit,
    current_sms_limit,
    expected_sms_limit,
):
    service_one["message_limit"] = current_limit
    service_one["sms_daily_limit"] = current_sms_limit
    client_request.login(platform_admin_user, service_one)
    client_request.post(
        "main.service_switch_live",
        service_id=SERVICE_ONE_ID,
        _data={"enabled": "True"},
        _expected_status=302,
        _expected_redirect=url_for(
            "main.service_settings",
            service_id=SERVICE_ONE_ID,
        ),
    )
    mock_update_service.assert_called_with(
        SERVICE_ONE_ID,
        message_limit=expected_limit,
        sms_daily_limit=expected_sms_limit,
        restricted=False,
        go_live_at="2017-04-01 11:09:00.061258",
    )


def test_show_live_service(
    client_request,
    mock_get_live_service,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
):
    page = client_request.get(
        "main.service_settings",
        service_id=SERVICE_ONE_ID,
    )
    assert page.find("h1").text.strip() == "Settings"
    assert "Your service is in trial mode" not in page.text
    assert url_for(".request_to_go_live", service_id=SERVICE_ONE_ID) not in page


@pytest.mark.parametrize(
    "restricted, go_live_user, expected_label",
    [
        (True, None, "Request to go live"),
        (True, "Service Manager User", "Request being reviewed"),
    ],
)
def test_show_live_banner(
    client_request,
    mock_get_live_service,
    single_reply_to_email_address,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
    platform_admin_user,
    service_one,
    restricted,
    go_live_user,
    expected_label,
):
    service_one["restricted"] = restricted
    service_one["go_live_user"] = go_live_user
    client_request.login(platform_admin_user, service_one)

    page = client_request.get(
        "main.service_settings",
        service_id=SERVICE_ONE_ID,
    )

    request_link = page.select_one('a[href*="request-to-go-live"]')
    assert expected_label in request_link.text.strip()

    live_banner = page.find("div", attrs={"id": "live-banner"})
    assert live_banner.text.strip() == "Trial"


@pytest.mark.parametrize(
    "current_limit, expected_limit, current_sms_limit, expected_sms_limit",
    [
        (42, 50, 33, 50),
        (50, 50, 50, 50),
        (50_000, 50, 3000, 50),
    ],
)
def test_switch_service_to_restricted(
    client_request,
    platform_admin_user,
    mock_get_live_service,
    mock_update_service,
    current_limit,
    expected_limit,
    current_sms_limit,
    expected_sms_limit,
    service_one,
):
    service_one["message_limit"] = current_limit
    service_one["sms_daily_limit"] = current_sms_limit
    client_request.login(platform_admin_user, service_one)
    client_request.post(
        "main.service_switch_live",
        service_id=SERVICE_ONE_ID,
        _data={"enabled": "False"},
        _expected_status=302,
        _expected_response=url_for(
            "main.service_settings",
            service_id=SERVICE_ONE_ID,
        ),
    )
    mock_update_service.assert_called_with(
        SERVICE_ONE_ID, message_limit=expected_limit, sms_daily_limit=expected_sms_limit, restricted=True, go_live_at=None
    )


@pytest.mark.parametrize(
    "count_as_live, selected, labelled",
    (
        (True, "True", "Yes"),
        (False, "False", "No"),
    ),
)
def test_show_switch_service_to_count_as_live_page(
    mocker,
    client_request,
    platform_admin_user,
    mock_update_service,
    count_as_live,
    selected,
    labelled,
):
    mocker.patch(
        "app.models.service.Service.count_as_live",
        create=True,
        new_callable=PropertyMock,
        return_value=count_as_live,
    )
    client_request.login(platform_admin_user)
    page = client_request.get(
        "main.service_switch_count_as_live",
        service_id=SERVICE_ONE_ID,
    )
    assert page.select_one("[checked]")["value"] == selected
    assert page.select_one("label[for={}]".format(page.select_one("[checked]")["id"])).text.strip() == labelled


@pytest.mark.parametrize(
    "post_data, expected_persisted_value",
    (
        ("True", True),
        ("False", False),
    ),
)
def test_switch_service_to_count_as_live(
    client_request,
    platform_admin_user,
    mock_update_service,
    post_data,
    expected_persisted_value,
):
    client_request.login(platform_admin_user)
    client_request.post(
        "main.service_switch_count_as_live",
        service_id=SERVICE_ONE_ID,
        _data={"enabled": post_data},
        _expected_status=302,
        _expected_redirect=url_for(
            "main.service_settings",
            service_id=SERVICE_ONE_ID,
        ),
    )
    mock_update_service.assert_called_with(
        SERVICE_ONE_ID,
        count_as_live=expected_persisted_value,
    )


def test_should_not_allow_duplicate_names(
    client_request,
    mock_service_name_is_not_unique,
    service_one,
):
    page = client_request.post(
        "main.service_name_change",
        service_id=SERVICE_ONE_ID,
        _data={"name": "SErvICE TWO"},
        _expected_status=200,
    )

    assert "This service name is already in use" in page.text
    app.service_api_client.is_service_name_unique.assert_called_once_with(
        SERVICE_ONE_ID,
        "SErvICE TWO",
    )


def test_should_show_service_name_confirmation(
    client_request,
):
    page = client_request.get(
        "main.service_name_change_confirm",
        service_id=SERVICE_ONE_ID,
    )
    assert "Change your service name" in page.text
    app.service_api_client.get_service.assert_called_with(SERVICE_ONE_ID)


def test_should_show_service_email_from_confirmation(
    client_request,
):
    page = client_request.get(
        "main.service_email_from_change_confirm",
        service_id=SERVICE_ONE_ID,
    )
    assert "Change your sending email address" in page.text
    app.service_api_client.get_service.assert_called_with(SERVICE_ONE_ID)


def test_should_redirect_after_service_name_confirmation(
    client_request,
    mock_update_service,
    mock_verify_password,
    mock_get_inbound_number_for_service,
):
    service_new_name = "New Name"
    with client_request.session_transaction() as session:
        session["service_name_change"] = service_new_name
    client_request.post(
        "main.service_name_change_confirm",
        service_id=SERVICE_ONE_ID,
        _expected_status=302,
        _expected_redirect=url_for(
            "main.service_settings",
            service_id=SERVICE_ONE_ID,
        ),
    )

    # Ensure flash message is set
    with client_request.session_transaction() as session:
        assert session["_flashes"][0][1] == "Setting updated"

    mock_update_service.assert_called_once_with(
        SERVICE_ONE_ID,
        name=service_new_name,
    )
    assert mock_verify_password.called is True


@pytest.mark.parametrize("sending_domain", [None, "test.example.com"])
def test_service_email_from_change(client_request, app_, sending_domain, active_user_with_permissions, service_one):
    sending_domain = sending_domain or app_.config["SENDING_DOMAIN"]
    service = service_one | {"sending_domain": sending_domain}
    client_request.login(active_user_with_permissions, service)

    page = client_request.get(
        "main.service_email_from_change",
        service_id=SERVICE_ONE_ID,
        _expected_status=200,
    )

    assert page.h1.text == "Change your sending email address"
    assert service["email_from"] in page.select_one("input")["value"]
    assert f"@{sending_domain}" in page.text


def test_should_redirect_after_service_email_from_confirmation(
    client_request,
    mock_update_service,
    mock_verify_password,
    mock_get_inbound_number_for_service,
):
    service_new_email_from = "new.email"
    with client_request.session_transaction() as session:
        session["service_email_from_change"] = service_new_email_from
    client_request.post(
        "main.service_email_from_change_confirm",
        service_id=SERVICE_ONE_ID,
        _expected_status=302,
        _expected_redirect=url_for(
            "main.service_settings",
            service_id=SERVICE_ONE_ID,
        ),
    )

    # Ensure flash message is set
    with client_request.session_transaction() as session:
        assert session["_flashes"][0][1] == "Setting updated"

    mock_update_service.assert_called_once_with(SERVICE_ONE_ID, email_from=email_safe(service_new_email_from))
    assert mock_verify_password.called is True


def test_should_raise_duplicate_name_handled(
    client_request,
    mock_update_service_raise_httperror_duplicate_name,
    mock_verify_password,
):
    with client_request.session_transaction() as session:
        session["service_name_change"] = "New Name"

    client_request.post(
        "main.service_name_change_confirm",
        service_id=SERVICE_ONE_ID,
        _expected_status=302,
        _expected_redirect=url_for(
            "main.service_name_change",
            service_id=SERVICE_ONE_ID,
        ),
    )

    assert mock_update_service_raise_httperror_duplicate_name.called
    assert mock_verify_password.called


@pytest.mark.parametrize(
    ("count_of_users_with_manage_service," "count_of_invites_with_manage_service," "expected_user_checklist_item"),
    [
        (1, 0, "Add a team member who can manage settings Not completed"),
        (2, 0, "Add a team member who can manage settings Completed"),
        (1, 1, "Add a team member who can manage settings In progress"),
    ],
)
@pytest.mark.parametrize(
    "count_of_templates, expected_templates_checklist_item",
    [
        (0, "Add templates with content you plan on sending Not completed"),
        (1, "Add templates with content you plan on sending Completed"),
        (2, "Add templates with content you plan on sending Completed"),
    ],
)
@pytest.mark.parametrize(
    "accepted_tos, expected_tos_checklist_item",
    [
        (False, "Accept the terms of use Not completed"),
        (True, "Accept the terms of use Completed"),
    ],
)
@pytest.mark.parametrize(
    "submitted_use_case, expected_use_case_checklist_item",
    [
        (False, "Tell us about how you intend to use GC Notify Not completed"),
        (True, "Tell us about how you intend to use GC Notify Completed"),
    ],
)
def test_request_to_go_live_page(
    active_user_with_permissions,
    active_user_no_settings_permission,
    client_request,
    mocker,
    service_one,
    fake_uuid,
    count_of_users_with_manage_service,
    count_of_invites_with_manage_service,
    expected_user_checklist_item,
    count_of_templates,
    expected_templates_checklist_item,
    accepted_tos,
    expected_tos_checklist_item,
    submitted_use_case,
    expected_use_case_checklist_item,
):
    user1 = create_active_user_with_permissions()
    user2 = create_active_user_no_settings_permission()
    mock_get_users = mocker.patch(
        "app.models.user.Users.client",
        return_value=([user1] * count_of_users_with_manage_service + [user2]),
    )
    mock_get_invites = mocker.patch(
        "app.models.user.InvitedUsers.client",
        return_value=(
            ([create_sample_invite(service_id=service_one.id, from_user=user1["id"])] * count_of_invites_with_manage_service)
            + [create_sample_invite(service_id=service_one.id, from_user=user2["id"], permissions="view_activity")]
        ),
    )

    mock_templates = mocker.patch(
        "app.models.service.Service.all_templates",
        new_callable=PropertyMock,
        return_value=list(range(0, count_of_templates)),
    )

    mocker.patch(
        "app.models.service.service_api_client.has_accepted_tos",
        return_value=accepted_tos,
    )

    mocker.patch(
        "app.models.service.service_api_client.has_submitted_use_case",
        return_value=submitted_use_case,
    )

    page = client_request.get("main.request_to_go_live", service_id=SERVICE_ONE_ID)
    assert page.h1.text == "Request to go live"

    tasks_links = [a["href"] for a in page.select(".task-list .task-list-item a")]

    assert tasks_links == [
        url_for("main.use_case", service_id=SERVICE_ONE_ID),
        url_for("main.choose_template", service_id=SERVICE_ONE_ID),
        url_for("main.manage_users", service_id=SERVICE_ONE_ID),
        url_for("main.terms_of_use", service_id=SERVICE_ONE_ID),
    ]

    checklist_items = [normalize_spaces(i.text) for i in page.select(".task-list .task-list-item")]

    assert checklist_items == [
        expected_use_case_checklist_item,
        expected_templates_checklist_item,
        expected_user_checklist_item,
        expected_tos_checklist_item,
    ]

    mock_get_users.assert_called_once_with(SERVICE_ONE_ID)
    if count_of_users_with_manage_service < 2:
        mock_get_invites.assert_called_once_with(SERVICE_ONE_ID)
    assert mock_templates.called is True


@pytest.mark.parametrize(
    "service_params, expected_sentence",
    [
        (
            {"restricted": True, "go_live_user": uuid4()},
            "The request to go live is being reviewed.",
        ),
        (
            {"restricted": True, "go_live_user": None},
            "Please contact your service manager.",
        ),
    ],
    ids=["service pending live", "trial service"],
)
def test_request_to_go_live_page_without_manage_service_permission(
    client_request, active_user_no_settings_permission, service_params, expected_sentence, service_one
):
    assert "manage_service" not in active_user_no_settings_permission["permissions"]

    service = service_one | service_params
    client_request.login(active_user_no_settings_permission, service)

    page = client_request.get(
        "main.request_to_go_live",
        service_id=SERVICE_ONE_ID,
        _expected_status=200,
    )

    assert page.h1.text == "Request to go live"
    assert page.select_one("#main_content p").text.strip() == expected_sentence

    tasks_links = [a["href"] for a in page.select(".task-list .task-list-item a")]
    assert tasks_links == []

    checklist_items = [normalize_spaces(i.text) for i in page.select(".task-list .task-list-item")]
    assert checklist_items == []


def test_request_to_go_live_terms_of_use_page(
    client_request,
    mocker,
):
    page = client_request.get("main.terms_of_use", service_id=SERVICE_ONE_ID)
    assert page.h1.text == "Accepting the terms of use"

    assert page.select_one(".back-link")["href"] == url_for("main.request_to_go_live", service_id=SERVICE_ONE_ID)

    # Form posts to the same endpoint
    assert page.select_one("form")["method"] == "post"
    assert "action" not in page.select_one("form")

    # Accepting the terms of use
    mock_accept_tos = mocker.patch("app.service_api_client.accept_tos")

    page = client_request.post(
        "main.terms_of_use",
        service_id=SERVICE_ONE_ID,
        _expected_status=302,
        _expected_redirect=url_for("main.request_to_go_live", service_id=SERVICE_ONE_ID),
    )

    mock_accept_tos.assert_called_once_with(SERVICE_ONE_ID)


def test_request_to_go_live_terms_of_use_page_without_permission(
    client_request,
    active_user_no_settings_permission,
):
    client_request.login(active_user_no_settings_permission)
    client_request.get(
        "main.terms_of_use",
        service_id=SERVICE_ONE_ID,
        _expected_status=403,
    )


def test_request_to_go_live_use_case_page(
    client_request,
    mocker,
):
    store_mock = mocker.patch("app.service_api_client.store_use_case_data")
    submit_use_case_mock = mocker.patch("app.service_api_client.register_submit_use_case")
    use_case_data_mock = mocker.patch("app.service_api_client.get_use_case_data")
    use_case_data_mock.return_value = None
    page = client_request.get(".use_case", service_id=SERVICE_ONE_ID)
    assert page.h1.text == "About your service"

    assert page.select_one(".back-link")["href"] == url_for(".request_to_go_live", service_id=SERVICE_ONE_ID)

    # Form posts to the same endpoint
    assert page.select_one("form")["method"] == "post"
    assert "action" not in page.select_one("form")

    # Posting first step without posting anything
    page = client_request.post(
        ".use_case",
        service_id=SERVICE_ONE_ID,
        _expected_status=200,
        _data={
            "department_org_name": "",
            "other_use_case": "",  # This one is optional
        },
    )

    assert submit_use_case_mock.call_count == 0
    assert store_mock.call_count == 1
    assert [(error["data-error-label"], normalize_spaces(error.text)) for error in page.select(".error-message")] == [
        ("department_org_name", "This field is required."),
        ("main_use_case", "This field is required."),
        ("intended_recipients", "This field is required."),
    ]

    page = client_request.post(
        ".use_case",
        service_id=SERVICE_ONE_ID,
        _expected_status=200,
        _data={
            "department_org_name": "Org name",
            "main_use_case": ["account_management"],
            "other_use_case": "Something else",
            "intended_recipients": ["public"],
        },
    )
    assert page.h1.text == "About your notifications"

    assert submit_use_case_mock.call_count == 0
    assert store_mock.call_count == 2
    expected_use_case_data = {
        "form_data": {
            "department_org_name": "Org name",
            "intended_recipients": ["public"],
            "main_use_case": ["account_management"],
            "other_use_case": "Something else",
            "daily_email_volume": None,
            "annual_email_volume": None,
            "daily_sms_volume": None,
            "annual_sms_volume": None,
            "exact_daily_email": None,
            "exact_daily_sms": None,
        },
        "step": "about-notifications",
    }
    store_mock.assert_called_with(SERVICE_ONE_ID, expected_use_case_data)

    # Fake that the form data and step have been stored and
    # map the return value as expected
    use_case_data_mock.reset_mock()
    use_case_data_mock.return_value = expected_use_case_data

    # On second step, can go back to step 1
    page = client_request.get(".use_case", service_id=SERVICE_ONE_ID)
    assert page.h1.text == "About your notifications"

    assert page.select_one("form")["method"] == "post"
    assert "action" not in page.select_one("form")

    assert page.select_one(".back-link")["href"] == url_for(".use_case", service_id=SERVICE_ONE_ID, current_step="about-service")

    # Submitting second and final step

    page = client_request.post(
        ".use_case",
        service_id=SERVICE_ONE_ID,
        _expected_status=302,
        _expected_redirect=url_for("main.request_to_go_live", service_id=SERVICE_ONE_ID),
        _data={
            "daily_email_volume": "0",
            "annual_email_volume": "within_limit",
            "daily_sms_volume": "more_sms",
            "annual_sms_volume": "above_limit",
            "exact_daily_email": 5,
            "exact_daily_sms": 25000,
            # Need to submit intended_recipients, main_use_case and any checkbox
            # again because otherwise the form thinks we removed checkbox values.
            # On the real form, these fields are hidden on the second step
            "main_use_case": expected_use_case_data["form_data"]["main_use_case"],
            "intended_recipients": expected_use_case_data["form_data"]["intended_recipients"],
        },
    )
    use_case_data_mock.assert_has_calls([call(SERVICE_ONE_ID), call(SERVICE_ONE_ID)])

    submit_use_case_mock.assert_called_once_with(SERVICE_ONE_ID)
    assert store_mock.call_count == 3
    store_mock.assert_called_with(
        SERVICE_ONE_ID,
        {
            "form_data": {
                "department_org_name": "Org name",
                "intended_recipients": ["public"],
                "main_use_case": ["account_management"],
                "other_use_case": "Something else",
                "daily_email_volume": "0",
                "annual_email_volume": "within_limit",
                "daily_sms_volume": "more_sms",
                "annual_sms_volume": "above_limit",
                "exact_daily_email": 0,
                "exact_daily_sms": 25000,
            },
            "step": "about-notifications",
        },
    )


@pytest.mark.parametrize(
    "salesforce_feature_flag, organisation_notes, organisation_question_visible",
    (
        (False, "Some department > Some group", True),
        (False, "", True),
        (True, "Some department > Some group", False),
        (True, "", True),
    ),
)
def test_request_to_go_live_use_case_page_hides_organisation(
    client_request: ClientRequest,
    mocker: MockerFixture,
    app_: Flask,
    service_one: Service,
    salesforce_feature_flag: bool,
    organisation_notes: str,
    organisation_question_visible: bool,
):
    with set_config(app_, "FF_SALESFORCE_CONTACT", salesforce_feature_flag):
        use_case_data_mock = mocker.patch("app.service_api_client.get_use_case_data")
        use_case_data_mock.return_value = None
        service_one.organisation_notes = organisation_notes  # type: ignore
        page = client_request.get(".use_case", service_id=service_one.id)
        organisation_question_visible_actual = page.body.find_all("label")[0].text.strip() == "Name of department or organisation"
        assert organisation_question_visible_actual == organisation_question_visible


def test_request_to_go_live_can_resume_use_case_page(
    client_request,
    mocker,
    mock_get_service_templates,
    mock_get_users_by_service,
    mock_get_invites_for_service,
):
    mocker.patch(
        "app.service_api_client.get_use_case_data",
        return_value={
            "form_data": {
                "department_org_name": "Org name",
                "intended_recipients": ["public"],
                "purpose": "Purpose",
            },
            "step": "about-notifications",
        },
    )

    # Can go back to use case form form request to go live page
    page = client_request.get(".request_to_go_live", service_id=SERVICE_ONE_ID)

    assert url_for(".use_case", service_id=SERVICE_ONE_ID) in [a["href"] for a in page.select(".task-list .task-list-item a")]

    # Going back to the use case page goes directly to step 2
    page = client_request.get(".use_case", service_id=SERVICE_ONE_ID)
    assert page.h1.text == "About your notifications"


def test_request_to_go_live_use_case_page_without_permission(
    client_request,
    active_user_no_settings_permission,
):
    client_request.login(active_user_no_settings_permission)
    client_request.get(
        "main.use_case",
        service_id=SERVICE_ONE_ID,
        _expected_status=403,
    )


@pytest.mark.parametrize("checklist_completed", (False, True))
def test_should_always_show_go_live_button(
    client_request: ClientRequest,
    mocker,
    mock_get_service_templates,
    mock_get_users_by_service,
    mock_get_invites_for_service,
    checklist_completed,
):
    mocker.patch(
        "app.models.service.Service.go_live_checklist_completed",
        new_callable=PropertyMock,
        return_value=checklist_completed,
    )

    page = client_request.get("main.request_to_go_live", service_id=SERVICE_ONE_ID)
    assert page.h1.text == "Request to go live"
    assert page.select_one("form")["method"] == "post"
    assert "action" not in page.select_one("form")
    page.select_one("[type=submit]").text.strip() == ("Request to go live")
    if checklist_completed:
        paragraphs = [normalize_spaces(p.text) for p in page.select("main p")]
        assert (
            "Once you have completed all the steps, submit your request to the GC Notify team. "
            "We’ll be in touch within 2 business days."
        ) in paragraphs
    else:
        paragraphs = [normalize_spaces(p.text) for p in page.select("main p")]
        assert "Once you complete all the steps, you'll be able to submit your request." in paragraphs


def test_should_show_error_if_go_live_not_completed(
    client_request: ClientRequest,
    mocker,
    mock_get_service_templates,
    mock_get_users_by_service,
    mock_get_invites_for_service,
):
    mocker.patch(
        "app.models.service.Service.go_live_checklist_completed",
        new_callable=PropertyMock,
        return_value=False,
    )

    page = client_request.post(
        "main.request_to_go_live",
        service_id=SERVICE_ONE_ID,
        _expected_status=200,
    )
    banner_text = page.select_one(".banner").text.strip()
    assert "You must complete these steps before submitting the request:" in banner_text


def test_non_gov_users_cant_request_to_go_live(
    client_request,
    api_nongov_user_active,
    mock_get_organisations,
):
    client_request.login(api_nongov_user_active)
    client_request.post(
        "main.request_to_go_live",
        service_id=SERVICE_ONE_ID,
        _expected_status=403,
    )


def test_submit_go_live_request(
    client_request,
    mocker,
    active_user_with_permissions,
    single_reply_to_email_address,
    mock_update_service,
    service_one,
):
    mocker.patch(
        "app.models.service.Service.go_live_checklist_completed",
        new_callable=PropertyMock,
        return_value=True,
    )
    mocker.patch(
        "app.service_api_client.get_use_case_data",
        return_value={
            "form_data": {
                "department_org_name": "Org name",
                "intended_recipients": ["public"],
                "main_use_case": ["account_management"],
                "other_use_case": "Something else",
                "daily_email_volume": "0",
                "annual_email_volume": "within_limit",
                "daily_sms_volume": "more_sms",
                "annual_sms_volume": "above_limit",
                "exact_daily_email": None,
                "exact_daily_sms": 25000,
            },
            "step": "about-notifications",
        },
    )
    mock_contact = mocker.patch("app.user_api_client.send_contact_request")

    page = client_request.post(
        "main.request_to_go_live",
        service_id=SERVICE_ONE_ID,
        _follow_redirects=True,
    )

    assert page.h1.text == "Settings"
    assert normalize_spaces(page.select_one(".banner-default").text) == ("Your request was submitted.")

    mock_update_service.assert_called_once_with(SERVICE_ONE_ID, go_live_user=active_user_with_permissions["id"])

    expected_data = {
        "name": "Test User",
        "department_org_name": "Org name",
        "service_url": f"http://localhost/services/{SERVICE_ONE_ID}",
        "support_type": "go_live_request",
        "service_id": SERVICE_ONE_ID,
        "service_name": "service one",
        "intended_recipients": "public",
        "main_use_case": ["account_management"],
        "other_use_case": "Something else",
        "email_address": "test@user.canada.ca",
        "daily_email_volume": "0",
        "annual_email_volume": "within_limit",
        "daily_sms_volume": "more_sms",
        "annual_sms_volume": "above_limit",
        "exact_daily_email": None,
        "exact_daily_sms": 25000,
    }

    mock_contact.assert_called_once_with(expected_data)


@pytest.mark.parametrize(
    "route, permissions",
    [
        ("main.service_settings", ["manage_service"]),
        ("main.service_name_change", ["manage_service"]),
        ("main.service_name_change_confirm", ["manage_service"]),
        ("main.service_email_from_change", ["manage_service"]),
        ("main.service_email_from_change_confirm", ["manage_service"]),
        ("main.request_to_go_live", ["manage_service"]),
        ("main.request_to_go_live", ["send_messages"]),
        ("main.use_case", ["manage_service"]),
        ("main.terms_of_use", ["manage_service"]),
        ("main.submit_request_to_go_live", ["manage_service"]),
        ("main.archive_service", ["manage_service"]),
        ("main.service_switch_upload_document", ["manage_service"]),
    ],
)
def test_route_permissions(
    mocker,
    app_,
    client,
    api_user_active,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    mock_get_invites_for_service,
    single_sms_sender,
    route,
    permissions,
    mock_get_service_settings_page_common,
    mock_get_service_templates,
):
    validate_route_permission(
        mocker,
        app_,
        "GET",
        200,
        url_for(route, service_id=service_one["id"]),
        permissions,
        api_user_active,
        service_one,
    )


@pytest.mark.parametrize(
    "route",
    [
        "main.service_settings",
        "main.service_name_change",
        "main.service_name_change_confirm",
        "main.service_email_from_change",
        "main.service_email_from_change_confirm",
        "main.use_case",
        "main.terms_of_use",
        "main.service_switch_live",
        "main.archive_service",
        "main.service_switch_upload_document",
    ],
)
def test_route_invalid_permissions(
    mocker,
    app_,
    client,
    api_user_active,
    service_one,
    route,
    mock_get_service_templates,
    mock_get_invites_for_service,
):
    validate_route_permission(
        mocker,
        app_,
        "GET",
        403,
        url_for(route, service_id=service_one["id"]),
        ["blah"],
        api_user_active,
        service_one,
    )


@pytest.mark.parametrize(
    "route",
    [
        "main.service_settings",
        "main.service_name_change",
        "main.service_name_change_confirm",
        "main.service_email_from_change",
        "main.service_email_from_change_confirm",
        "main.request_to_go_live",
        "main.use_case",
        "main.terms_of_use",
    ],
)
def test_route_for_platform_admin(
    mocker,
    app_,
    client,
    platform_admin_user,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    route,
    mock_get_service_settings_page_common,
    mock_get_service_templates,
    mock_get_invites_for_service,
):
    validate_route_permission(
        mocker,
        app_,
        "GET",
        200,
        url_for(route, service_id=service_one["id"]),
        [],
        platform_admin_user,
        service_one,
    )


def test_and_more_hint_appears_on_settings_with_more_than_just_a_single_sender(
    client_request,
    service_one,
    multiple_reply_to_email_addresses,
    multiple_letter_contact_blocks,
    mock_get_service_organisation,
    multiple_sms_senders,
    mock_get_service_settings_page_common,
    app_,
):
    service_one["permissions"] = ["email", "sms"]

    page = client_request.get("main.service_settings", service_id=service_one["id"])

    def get_row(page, index):
        return normalize_spaces(page.select("tbody tr")[index].text)

    assert get_row(page, 5) == "Reply-to addresses test@example.com …and 2 more Manage Reply-to addresses"


@pytest.mark.parametrize(
    "sender_list_page, index, expected_output",
    [
        ("main.service_email_reply_to", 0, "test@example.com (default) Change"),
        ("main.service_letter_contact_details", 1, "1 Example Street (default) Change"),
    ],
)
def test_api_ids_dont_show_on_option_pages_with_a_single_sender(
    client_request,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    sender_list_page,
    index,
    expected_output,
):
    rows = client_request.get(sender_list_page, service_id=SERVICE_ONE_ID).select(".user-list-item")

    assert normalize_spaces(rows[index].text) == expected_output
    assert len(rows) == index + 1


@pytest.mark.parametrize(
    ("sender_list_page, endpoint_to_mock, sample_data, expected_items, is_platform_admin"),
    [
        (
            "main.service_email_reply_to",
            "app.service_api_client.get_reply_to_email_addresses",
            create_multiple_email_reply_to_addresses(),
            [
                "test@example.com (default) Change 1234",
                "test2@example.com Change 5678",
                "test3@example.com Change 9457",
            ],
            False,
        ),
        (
            "main.service_letter_contact_details",
            "app.service_api_client.get_letter_contacts",
            create_multiple_letter_contact_blocks(),
            [
                "Blank Make default",
                "1 Example Street (default) Change 1234",
                "2 Example Street Change 5678",
                "3 Example Street Change 9457",
            ],
            False,
        ),
        (
            "main.service_sms_senders",
            "app.service_api_client.get_sms_senders",
            create_multiple_sms_senders(),
            [
                "Example (default and receives replies) Change 1234",
                "Example 2 Change 5678",
                "Example 3 Change 9457",
            ],
            True,
        ),
    ],
)
def test_default_option_shows_for_default_sender(
    client_request,
    platform_admin_user,
    mocker,
    sender_list_page,
    endpoint_to_mock,
    sample_data,
    expected_items,
    is_platform_admin,
):
    mocker.patch(endpoint_to_mock, return_value=sample_data)

    if is_platform_admin:
        client_request.login(platform_admin_user)

    rows = client_request.get(sender_list_page, service_id=SERVICE_ONE_ID).select(".user-list-item")

    assert [normalize_spaces(row.text) for row in rows] == expected_items


def test_remove_default_from_default_letter_contact_block(
    client_request,
    mocker,
    multiple_letter_contact_blocks,
    mock_update_letter_contact,
):
    letter_contact_details_page = url_for(
        "main.service_letter_contact_details",
        service_id=SERVICE_ONE_ID,
    )

    link = client_request.get_url(letter_contact_details_page).select_one(".user-list-item a")
    assert link.text == "Make default"
    assert link["href"] == url_for(
        ".service_make_blank_default_letter_contact",
        service_id=SERVICE_ONE_ID,
    )

    client_request.get_url(
        link["href"],
        _expected_status=302,
        _expected_redirect=letter_contact_details_page,
    )

    mock_update_letter_contact.assert_called_once_with(
        SERVICE_ONE_ID,
        letter_contact_id="1234",
        contact_block="1 Example Street",
        is_default=False,
    )


@pytest.mark.parametrize(
    "sender_list_page, endpoint_to_mock, expected_output, is_platform_admin",
    [
        (
            "main.service_email_reply_to",
            "app.service_api_client.get_reply_to_email_addresses",
            "You have not added any reply-to email addresses yet",
            False,
        ),
        ("main.service_letter_contact_details", "app.service_api_client.get_letter_contacts", "Blank (default)", False),
        (
            "main.service_sms_senders",
            "app.service_api_client.get_sms_senders",
            "You have not added any text message senders yet",
            True,
        ),
    ],
)
def test_no_senders_message_shows(
    client_request,
    platform_admin_user,
    sender_list_page,
    endpoint_to_mock,
    expected_output,
    is_platform_admin,
    mocker,
):
    mocker.patch(endpoint_to_mock, return_value=[])

    if is_platform_admin:
        client_request.login(platform_admin_user)

    rows = client_request.get(sender_list_page, service_id=SERVICE_ONE_ID).select(".user-list-item")

    assert normalize_spaces(rows[0].text) == expected_output
    assert len(rows) == 1


@pytest.mark.parametrize(
    "reply_to_input, expected_error",
    [
        ("", "Enter an email address"),
        ("testtest", "Enter a valid email address"),
    ],
)
def test_incorrect_reply_to_email_address_input(reply_to_input, expected_error, client_request, no_reply_to_email_addresses):
    page = client_request.post(
        "main.service_add_email_reply_to",
        service_id=SERVICE_ONE_ID,
        _data={"email_address": reply_to_input},
        _expected_status=200,
    )

    assert normalize_spaces(page.select_one(".error-message").text) == expected_error


@pytest.mark.parametrize(
    "contact_block_input, expected_error",
    [
        ("", "This cannot be empty"),
        (
            "1 \n 2 \n 3 \n 4 \n 5 \n 6 \n 7 \n 8 \n 9 \n 0 \n a",
            "Contains 11 lines, maximum is 10",
        ),
    ],
)
def test_incorrect_letter_contact_block_input(contact_block_input, expected_error, client_request, no_letter_contact_blocks):
    page = client_request.post(
        "main.service_add_letter_contact",
        service_id=SERVICE_ONE_ID,
        _data={"letter_contact_block": contact_block_input},
        _expected_status=200,
    )

    assert normalize_spaces(page.select_one(".error-message").text) == expected_error


@pytest.mark.parametrize(
    "sms_sender_input, expected_error",
    [
        ("elevenchars", None),
        ("11 chars", None),
        ("", "This cannot be empty"),
        ("abcdefghijkhgkg", "Enter 11 characters or fewer"),
        (r" ¯\_(ツ)_/¯ ", "Use letters and numbers only"),
        ("blood.co.uk", None),
        ("00123", "Can't start with 00"),
    ],
)
def test_incorrect_sms_sender_input(
    sms_sender_input,
    expected_error,
    client_request,
    no_sms_senders,
    mock_add_sms_sender,
    platform_admin_user,
):
    client_request.login(platform_admin_user)

    page = client_request.post(
        "main.service_add_sms_sender",
        service_id=SERVICE_ONE_ID,
        _data={"sms_sender": sms_sender_input},
        _expected_status=(200 if expected_error else 302),
    )

    error_message = page.select_one(".error-message")
    count_of_api_calls = len(mock_add_sms_sender.call_args_list)

    if not expected_error:
        assert not error_message
        assert count_of_api_calls == 1
    else:
        assert normalize_spaces(error_message.text) == expected_error
        assert count_of_api_calls == 0


@pytest.mark.parametrize(
    "reply_to_addresses, data, api_default_args",
    [
        ([], {}, True),
        (create_multiple_email_reply_to_addresses(), {}, False),
        (create_multiple_email_reply_to_addresses(), {"is_default": "y"}, True),
    ],
)
def test_add_reply_to_email_address_sends_test_notification(mocker, client_request, reply_to_addresses, data, api_default_args):
    mocker.patch("app.service_api_client.get_reply_to_email_addresses", return_value=reply_to_addresses)
    data["email_address"] = "test@example.com"
    mock_verify = mocker.patch(
        "app.service_api_client.verify_reply_to_email_address",
        return_value={"data": {"id": "123"}},
    )
    client_request.post(
        "main.service_add_email_reply_to",
        service_id=SERVICE_ONE_ID,
        _data=data,
        _expected_status=302,
        _expected_redirect=url_for(
            "main.service_verify_reply_to_address",
            service_id=SERVICE_ONE_ID,
            notification_id="123",
        )
        + "?is_default={}".format(api_default_args),
    )
    mock_verify.assert_called_once_with(SERVICE_ONE_ID, "test@example.com")


@pytest.mark.parametrize(
    "is_default,replace,expected_header",
    [(True, "&replace=123", "Change"), (False, "", "Add")],
)
@pytest.mark.parametrize(
    "status,expected_failure,expected_success",
    [
        ("delivered", 0, 1),
        ("sending", 0, 0),
        ("permanent-failure", 1, 0),
    ],
)
@freeze_time("2018-06-01 11:11:00.061258")
def test_service_verify_reply_to_address(
    mocker,
    client_request,
    fake_uuid,
    get_non_default_reply_to_email_address,
    status,
    expected_failure,
    expected_success,
    is_default,
    replace,
    expected_header,
):
    notification = {
        "id": fake_uuid,
        "status": status,
        "to": "email@example.canada.ca",
        "service_id": SERVICE_ONE_ID,
        "template_id": TEMPLATE_ONE_ID,
        "notification_type": "email",
        "created_at": "2018-06-01T11:10:52.499230+00:00",
    }
    mocker.patch("app.notification_api_client.get_notification", return_value=notification)
    mock_add_reply_to_email_address = mocker.patch("app.service_api_client.add_reply_to_email_address")
    mock_update_reply_to_email_address = mocker.patch("app.service_api_client.update_reply_to_email_address")
    mocker.patch("app.service_api_client.get_reply_to_email_addresses", return_value=[])
    page = client_request.get(
        "main.service_verify_reply_to_address",
        service_id=SERVICE_ONE_ID,
        notification_id=notification["id"],
        _optional_args="?is_default={}{}".format(is_default, replace),
    )
    assert page.find("h1").text == "{} reply-to email address".format(expected_header)
    if replace:
        assert "/email-reply-to/123/edit" in page.find("a", text="Back").attrs["href"]
    else:
        assert "/email-reply-to/add" in page.find("a", text="Back").attrs["href"]

    assert len(page.find_all("div", class_="banner-dangerous")) == expected_failure
    assert len(page.find_all("div", class_="banner-default-with-tick")) == expected_success

    if status == "delivered":
        if replace:
            mock_update_reply_to_email_address.assert_called_once_with(
                SERVICE_ONE_ID,
                "123",
                email_address=notification["to"],
                is_default=is_default,
            )
            mock_add_reply_to_email_address.assert_not_called()
        else:
            mock_add_reply_to_email_address.assert_called_once_with(
                SERVICE_ONE_ID, email_address=notification["to"], is_default=is_default
            )
            mock_update_reply_to_email_address.assert_not_called()
    else:
        mock_add_reply_to_email_address.assert_not_called()
    if status == "permanent-failure":
        assert page.find("input", type="email").attrs["value"] == notification["to"]


@freeze_time("2018-06-01 11:11:00.061258")
def test_add_reply_to_email_address_fails_if_notification_not_delivered_in_45_sec(mocker, client_request, fake_uuid):
    notification = {
        "id": fake_uuid,
        "status": "sending",
        "to": "email@example.canada.ca",
        "service_id": SERVICE_ONE_ID,
        "template_id": TEMPLATE_ONE_ID,
        "notification_type": "email",
        "created_at": "2018-06-01T11:10:12.499230+00:00",
    }
    mocker.patch("app.service_api_client.get_reply_to_email_addresses", return_value=[])
    mocker.patch("app.notification_api_client.get_notification", return_value=notification)
    mock_add_reply_to_email_address = mocker.patch("app.service_api_client.add_reply_to_email_address")
    page = client_request.get(
        "main.service_verify_reply_to_address",
        service_id=SERVICE_ONE_ID,
        notification_id=notification["id"],
        _optional_args="?is_default={}".format(False),
    )
    expected_banner = page.find_all("div", class_="banner-dangerous")[0]
    assert "There’s a problem with your reply-to address" in expected_banner.text.strip()
    mock_add_reply_to_email_address.assert_not_called()


@pytest.mark.parametrize(
    "letter_contact_blocks, data, api_default_args",
    [
        ([], {}, True),  # no existing letter contact blocks
        (create_multiple_letter_contact_blocks(), {}, False),
        (create_multiple_letter_contact_blocks(), {"is_default": "y"}, True),
    ],
)
def test_add_letter_contact(letter_contact_blocks, data, api_default_args, mocker, client_request, mock_add_letter_contact):
    mocker.patch("app.service_api_client.get_letter_contacts", return_value=letter_contact_blocks)

    data["letter_contact_block"] = "1 Example Street"
    client_request.post("main.service_add_letter_contact", service_id=SERVICE_ONE_ID, _data=data)

    mock_add_letter_contact.assert_called_once_with(SERVICE_ONE_ID, contact_block="1 Example Street", is_default=api_default_args)


def test_add_letter_contact_when_coming_from_template(
    no_letter_contact_blocks,
    client_request,
    mock_add_letter_contact,
    fake_uuid,
    mock_get_service_letter_template,
    mock_update_service_template_sender,
):
    page = client_request.get(
        "main.service_add_letter_contact",
        service_id=SERVICE_ONE_ID,
        from_template=fake_uuid,
    )

    assert page.select_one(".back-link")["href"] == url_for(
        "main.view_template",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
    )

    client_request.post(
        "main.service_add_letter_contact",
        service_id=SERVICE_ONE_ID,
        _data={
            "letter_contact_block": "1 Example Street",
        },
        from_template=fake_uuid,
        _expected_redirect=url_for(
            "main.view_template",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )

    mock_add_letter_contact.assert_called_once_with(
        SERVICE_ONE_ID,
        contact_block="1 Example Street",
        is_default=True,
    )
    mock_update_service_template_sender.assert_called_once_with(
        SERVICE_ONE_ID,
        fake_uuid,
        "1234",
    )


@pytest.mark.parametrize(
    "sms_senders, data, api_default_args",
    [([], {}, True), (create_multiple_sms_senders(), {}, False), (create_multiple_sms_senders(), {"is_default": "y"}, True)],
)
def test_add_sms_sender(sms_senders, data, api_default_args, mocker, client_request, mock_add_sms_sender, platform_admin_user):
    client_request.login(platform_admin_user)

    mocker.patch("app.service_api_client.get_sms_senders", return_value=sms_senders)
    data["sms_sender"] = "Example"
    client_request.post("main.service_add_sms_sender", service_id=SERVICE_ONE_ID, _data=data)

    mock_add_sms_sender.assert_called_once_with(SERVICE_ONE_ID, sms_sender="Example", is_default=api_default_args)


@pytest.mark.parametrize(
    "sender_page, function_to_mock, data,  checkbox_present",
    [
        ("main.service_add_email_reply_to", "app.service_api_client.get_reply_to_email_addresses", [], False),
        (
            "main.service_add_email_reply_to",
            "app.service_api_client.get_reply_to_email_addresses",
            create_multiple_email_reply_to_addresses(),
            True,
        ),
        ("main.service_add_letter_contact", "app.service_api_client.get_letter_contacts", [], False),
        (
            "main.service_add_letter_contact",
            "app.service_api_client.get_letter_contacts",
            create_multiple_letter_contact_blocks(),
            True,
        ),
    ],
)
def test_default_box_doesnt_show_on_first_sender(sender_page, function_to_mock, mocker, data, checkbox_present, client_request):
    mocker.patch(function_to_mock, side_effect=lambda service_id: data)

    page = client_request.get(sender_page, service_id=SERVICE_ONE_ID)

    assert bool(page.select_one("[name=is_default]")) == checkbox_present


@pytest.mark.parametrize(
    "reply_to_address, data, api_default_args",
    [
        (create_reply_to_email_address(), {"is_default": "y"}, True),
        (create_reply_to_email_address(), {}, True),
        (create_reply_to_email_address(is_default=False), {}, False),
        (create_reply_to_email_address(is_default=False), {"is_default": "y"}, True),
    ],
)
def test_edit_reply_to_email_address_sends_verification_notification_if_address_is_changed(
    reply_to_address,
    data,
    api_default_args,
    mocker,
    fake_uuid,
    client_request,
):
    mock_verify = mocker.patch(
        "app.service_api_client.verify_reply_to_email_address",
        return_value={"data": {"id": "123"}},
    )
    mocker.patch("app.service_api_client.get_reply_to_email_address", return_value=reply_to_address)
    data["email_address"] = "test@tbs-sct.gc.ca"
    client_request.post(
        "main.service_edit_email_reply_to",
        service_id=SERVICE_ONE_ID,
        reply_to_email_id=fake_uuid,
        _data=data,
    )
    mock_verify.assert_called_once_with(SERVICE_ONE_ID, "test@tbs-sct.gc.ca")


@pytest.mark.parametrize(
    "reply_to_address, data, api_default_args",
    [
        (create_reply_to_email_address(), {"is_default": "y"}, True),
        (create_reply_to_email_address(), {}, True),
        (create_reply_to_email_address(is_default=False), {}, False),
        (create_reply_to_email_address(is_default=False), {"is_default": "y"}, True),
    ],
)
def test_edit_reply_to_email_address_goes_straight_to_update_if_address_not_changed(
    reply_to_address,
    data,
    api_default_args,
    mocker,
    fake_uuid,
    client_request,
    mock_update_reply_to_email_address,
):
    mocker.patch("app.service_api_client.get_reply_to_email_address", return_value=reply_to_address)

    mock_verify = mocker.patch("app.service_api_client.verify_reply_to_email_address")
    data["email_address"] = "test@example.com"
    client_request.post(
        "main.service_edit_email_reply_to",
        service_id=SERVICE_ONE_ID,
        reply_to_email_id=fake_uuid,
        _data=data,
    )

    mock_update_reply_to_email_address.assert_called_once_with(
        SERVICE_ONE_ID,
        reply_to_email_id=fake_uuid,
        email_address="test@example.com",
        is_default=api_default_args,
    )
    mock_verify.assert_not_called()


@pytest.mark.parametrize(
    "sender_details",
    [create_reply_to_email_address(is_default=False), create_reply_to_email_address()],
)
def test_always_shows_delete_link_for_email_reply_to_address(
    mocker: MockerFixture,
    sender_details,
    fake_uuid,
    client_request,
):
    mocker.patch("app.service_api_client.get_reply_to_email_address", return_value=sender_details)
    partial_href = partial(
        url_for,
        "main.service_confirm_delete_email_reply_to",
        reply_to_email_id=sample_uuid(),
    )
    page = client_request.get(
        "main.service_edit_email_reply_to",
        service_id=SERVICE_ONE_ID,
        reply_to_email_id=sample_uuid(),
    )

    assert page.select_one(".back-link").text.strip() == "Back"
    assert page.select_one(".back-link")["href"] == url_for(
        ".service_email_reply_to",
        service_id=SERVICE_ONE_ID,
    )

    link = page.select_one(".page-footer a")
    assert normalize_spaces(link.text) == "Delete"
    assert link["href"] == partial_href(service_id=SERVICE_ONE_ID)


def test_confirm_delete_reply_to_email_address(fake_uuid, client_request, get_non_default_reply_to_email_address):
    page = client_request.get(
        "main.service_confirm_delete_email_reply_to",
        service_id=SERVICE_ONE_ID,
        reply_to_email_id=fake_uuid,
        _test_page_title=False,
    )

    assert normalize_spaces(page.select_one(".banner-dangerous").text) == (
        "Are you sure you want to delete this reply-to email address? " "Yes, delete"
    )
    assert "action" not in page.select_one(".banner-dangerous form")
    assert page.select_one(".banner-dangerous form")["method"] == "post"


def test_confirm_delete_default_reply_to_email_address(
    mocker: MockerFixture, fake_uuid, client_request, get_default_reply_to_email_address
):
    reply_tos = create_multiple_email_reply_to_addresses()
    reply_to_for_deletion = reply_tos[1]
    mocker.patch("app.models.service.Service.count_email_reply_to_addresses", len(reply_tos))
    mocker.patch("app.models.service.Service.email_reply_to_addresses", reply_tos)
    mocker.patch("app.models.service.Service.get_email_reply_to_address", return_value=reply_to_for_deletion)
    page = client_request.get(
        "main.service_confirm_delete_email_reply_to",
        service_id=SERVICE_ONE_ID,
        reply_to_email_id=reply_to_for_deletion["id"],
        _test_page_title=False,
    )

    assert normalize_spaces(page.select_one(".banner-dangerous").text) == (
        "Are you sure you want to delete this reply-to email address? " "Yes, delete"
    )
    assert "action" not in page.select_one(".banner-dangerous form")
    assert page.select_one(".banner-dangerous form")["method"] == "post"


def test_delete_reply_to_email_address(
    client_request: ClientRequest,
    service_one,
    fake_uuid,
    get_non_default_reply_to_email_address,
    mocker: MockerFixture,
):
    mock_delete = mocker.patch("app.service_api_client.delete_reply_to_email_address")
    client_request.post(
        ".service_delete_email_reply_to",
        service_id=SERVICE_ONE_ID,
        reply_to_email_id=fake_uuid,
        _expected_redirect=url_for(
            "main.service_email_reply_to",
            service_id=SERVICE_ONE_ID,
        ),
    )
    mock_delete.assert_called_once_with(service_id=SERVICE_ONE_ID, reply_to_email_id=fake_uuid)


def test_delete_default_reply_to_email_address_switches_default(
    client_request: ClientRequest, mocker: MockerFixture, service_one
):
    mock_delete = mocker.patch("app.service_api_client.delete_reply_to_email_address")
    mock_update = mocker.patch("app.service_api_client.update_reply_to_email_address")
    reply_to_1 = create_reply_to_email_address(service_id=service_one["id"], email_address="default@example.com", is_default=True)
    reply_to_2 = create_reply_to_email_address(service_id=service_one["id"], email_address="test@example.com", is_default=False)
    mocker.patch("app.models.service.Service.get_email_reply_to_address", return_value=reply_to_1)
    mocker.patch("app.models.service.Service.count_email_reply_to_addresses", 2)
    mocker.patch("app.models.service.Service.email_reply_to_addresses", [reply_to_1, reply_to_2])
    client_request.post(
        ".service_delete_email_reply_to",
        service_id=service_one["id"],
        reply_to_email_id=reply_to_1["id"],
        _expected_redirect=url_for(
            "main.service_email_reply_to",
            service_id=service_one["id"],
        ),
    )

    mock_update.assert_called_once_with(
        service_one["id"], email_address=reply_to_2["email_address"], reply_to_email_id=reply_to_2["id"], is_default=True
    )

    mock_delete.assert_called_once_with(service_id=service_one["id"], reply_to_email_id=reply_to_1["id"])


@pytest.mark.parametrize(
    "letter_contact_block, data, api_default_args",
    [
        (create_letter_contact_block(), {"is_default": "y"}, True),
        (create_letter_contact_block(), {}, True),
        (create_letter_contact_block(is_default=False), {}, False),
        (create_letter_contact_block(is_default=False), {"is_default": "y"}, True),
    ],
)
def test_edit_letter_contact_block(
    letter_contact_block,
    data,
    api_default_args,
    mocker,
    fake_uuid,
    client_request,
    mock_update_letter_contact,
):
    mocker.patch("app.service_api_client.get_letter_contact", return_value=letter_contact_block)

    data["letter_contact_block"] = "1 Example Street"
    client_request.post(
        "main.service_edit_letter_contact",
        service_id=SERVICE_ONE_ID,
        letter_contact_id=fake_uuid,
        _data=data,
    )

    mock_update_letter_contact.assert_called_once_with(
        SERVICE_ONE_ID,
        letter_contact_id=fake_uuid,
        contact_block="1 Example Street",
        is_default=api_default_args,
    )


def test_confirm_delete_letter_contact_block(
    fake_uuid,
    client_request,
    get_default_letter_contact_block,
):
    page = client_request.get(
        "main.service_confirm_delete_letter_contact",
        service_id=SERVICE_ONE_ID,
        letter_contact_id=fake_uuid,
        _test_page_title=False,
    )

    assert normalize_spaces(page.select_one(".banner-dangerous").text) == (
        "Are you sure you want to delete this contact block? " "Yes, delete"
    )
    assert "action" not in page.select_one(".banner-dangerous form")
    assert page.select_one(".banner-dangerous form")["method"] == "post"


def test_delete_letter_contact_block(
    client_request,
    service_one,
    fake_uuid,
    mocker,
):
    mock_delete = mocker.patch("app.service_api_client.delete_letter_contact")
    client_request.post(
        ".service_delete_letter_contact",
        service_id=SERVICE_ONE_ID,
        letter_contact_id=fake_uuid,
        _expected_redirect=url_for(
            "main.service_letter_contact_details",
            service_id=SERVICE_ONE_ID,
        ),
    )
    mock_delete.assert_called_once_with(
        service_id=SERVICE_ONE_ID,
        letter_contact_id=fake_uuid,
    )


@pytest.mark.parametrize(
    "sms_sender, data, api_default_args",
    [
        (create_sms_sender(), {"is_default": "y", "sms_sender": "test"}, True),
        (create_sms_sender(), {"sms_sender": "test"}, True),
        (create_sms_sender(is_default=False), {"sms_sender": "test"}, False),
        (create_sms_sender(is_default=False), {"is_default": "y", "sms_sender": "test"}, True),
    ],
)
def test_edit_sms_sender(
    sms_sender,
    data,
    api_default_args,
    mocker,
    fake_uuid,
    client_request,
    mock_update_sms_sender,
    platform_admin_user,
):
    client_request.login(platform_admin_user)

    mocker.patch("app.service_api_client.get_sms_sender", return_value=sms_sender)

    client_request.post(
        "main.service_edit_sms_sender",
        service_id=SERVICE_ONE_ID,
        sms_sender_id=fake_uuid,
        _data=data,
    )

    mock_update_sms_sender.assert_called_once_with(
        SERVICE_ONE_ID,
        sms_sender_id=fake_uuid,
        sms_sender="test",
        is_default=api_default_args,
    )


@pytest.mark.parametrize(
    "sender_page, endpoint_to_mock, sender_details, default_message, params, checkbox_present, is_platform_admin",
    [
        (
            "main.service_edit_email_reply_to",
            "app.service_api_client.get_reply_to_email_address",
            create_reply_to_email_address(),
            "This is the default reply-to address for service one emails",
            "reply_to_email_id",
            False,
            False,
        ),
        (
            "main.service_edit_email_reply_to",
            "app.service_api_client.get_reply_to_email_address",
            create_reply_to_email_address(is_default=False),
            "This is the default reply-to address for service one emails",
            "reply_to_email_id",
            True,
            False,
        ),
        (
            "main.service_edit_letter_contact",
            "app.service_api_client.get_letter_contact",
            create_letter_contact_block(),
            "This is currently your default address for service one.",
            "letter_contact_id",
            False,
            False,
        ),
        (
            "main.service_edit_letter_contact",
            "app.service_api_client.get_letter_contact",
            create_letter_contact_block(is_default=False),
            "THIS TEXT WONT BE TESTED",
            "letter_contact_id",
            True,
            False,
        ),
        (
            "main.service_edit_sms_sender",
            "app.service_api_client.get_sms_sender",
            create_sms_sender(),
            "This is the default text message sender.",
            "sms_sender_id",
            False,
            True,
        ),
        (
            "main.service_edit_sms_sender",
            "app.service_api_client.get_sms_sender",
            create_sms_sender(is_default=False),
            "This is the default text message sender.",
            "sms_sender_id",
            True,
            True,
        ),
    ],
)
def test_default_box_shows_on_non_default_sender_details_while_editing(
    fake_uuid,
    mocker,
    sender_page,
    endpoint_to_mock,
    sender_details,
    client_request,
    platform_admin_user,
    default_message,
    checkbox_present,
    is_platform_admin,
    params,
):
    page_arguments = {"service_id": SERVICE_ONE_ID}
    page_arguments[params] = fake_uuid

    mocker.patch(endpoint_to_mock, return_value=sender_details)
    # mocker.patch(function_to_mock, side_effect=lambda service_id: data)

    if is_platform_admin:
        client_request.login(platform_admin_user)

    page = client_request.get(sender_page, **page_arguments)

    if checkbox_present:
        assert page.select_one("[name=is_default]")
    else:
        assert normalize_spaces(page.select_one("form p").text) == (default_message)


@pytest.mark.parametrize(
    "sms_sender, expected_link_text, partial_href",
    [
        (
            create_sms_sender(is_default=False),
            "Delete",
            partial(url_for, "main.service_confirm_delete_sms_sender", sms_sender_id=sample_uuid()),
        ),
        (
            create_sms_sender(is_default=True),
            None,
            None,
        ),
    ],
)
def test_shows_delete_link_for_sms_sender(
    mocker,
    sms_sender,
    expected_link_text,
    partial_href,
    fake_uuid,
    client_request,
    platform_admin_user,
):
    mocker.patch("app.service_api_client.get_sms_sender", return_value=sms_sender)

    client_request.login(platform_admin_user)

    page = client_request.get(
        "main.service_edit_sms_sender",
        service_id=SERVICE_ONE_ID,
        sms_sender_id=sample_uuid(),
    )

    link = page.select_one(".page-footer a")
    back_link = page.select_one(".back-link")

    assert back_link.text.strip() == "Back"
    assert back_link["href"] == url_for(
        ".service_sms_senders",
        service_id=SERVICE_ONE_ID,
    )

    if expected_link_text:
        assert normalize_spaces(link.text) == expected_link_text
        assert link["href"] == partial_href(service_id=SERVICE_ONE_ID)
    else:
        assert not link


def test_confirm_delete_sms_sender(
    fake_uuid,
    client_request,
    platform_admin_user,
    get_non_default_sms_sender,
):
    client_request.login(platform_admin_user)

    page = client_request.get(
        "main.service_confirm_delete_sms_sender",
        service_id=SERVICE_ONE_ID,
        sms_sender_id=fake_uuid,
        _test_page_title=False,
    )

    assert normalize_spaces(page.select_one(".banner-dangerous").text) == (
        "Are you sure you want to delete this text message sender? " "Yes, delete"
    )
    assert "action" not in page.select_one(".banner-dangerous form")
    assert page.select_one(".banner-dangerous form")["method"] == "post"


@pytest.mark.parametrize(
    "sms_sender, expected_link_text",
    [
        (create_sms_sender(is_default=False, inbound_number_id="1234"), None),
        (create_sms_sender(is_default=True), None),
        (create_sms_sender(is_default=False), "Delete"),
    ],
)
def test_inbound_sms_sender_is_not_deleteable(
    client_request,
    platform_admin_user,
    service_one,
    fake_uuid,
    sms_sender,
    expected_link_text,
    mocker,
):
    mocker.patch("app.service_api_client.get_sms_sender", return_value=sms_sender)

    client_request.login(platform_admin_user)
    page = client_request.get(
        ".service_edit_sms_sender",
        service_id=SERVICE_ONE_ID,
        sms_sender_id="1234",
    )

    back_link = page.select_one(".back-link")
    footer_link = page.select_one(".page-footer a")
    assert normalize_spaces(back_link.text) == "Back"

    if expected_link_text:
        assert normalize_spaces(footer_link.text) == expected_link_text
    else:
        assert not footer_link


def test_delete_sms_sender(
    client_request,
    service_one,
    fake_uuid,
    get_non_default_sms_sender,
    mocker,
):
    mock_delete = mocker.patch("app.service_api_client.delete_sms_sender")
    client_request.post(
        ".service_delete_sms_sender",
        service_id=SERVICE_ONE_ID,
        sms_sender_id="1234",
        _expected_redirect=url_for(
            "main.service_sms_senders",
            service_id=SERVICE_ONE_ID,
        ),
    )
    mock_delete.assert_called_once_with(service_id=SERVICE_ONE_ID, sms_sender_id="1234")


@pytest.mark.parametrize(
    "sms_sender, hide_textbox",
    [
        (create_sms_sender(is_default=False, inbound_number_id="1234"), True),
        (create_sms_sender(is_default=True), False),
    ],
)
def test_inbound_sms_sender_is_not_editable(
    client_request,
    platform_admin_user,
    service_one,
    fake_uuid,
    sms_sender,
    hide_textbox,
    mocker,
):
    mocker.patch("app.service_api_client.get_sms_sender", return_value=sms_sender)

    client_request.login(platform_admin_user)
    page = client_request.get(
        ".service_edit_sms_sender",
        service_id=SERVICE_ONE_ID,
        sms_sender_id=fake_uuid,
    )

    assert bool(page.find("input", attrs={"name": "sms_sender"})) != hide_textbox
    if hide_textbox:
        assert (
            normalize_spaces(page.select_one('form[method="post"] p').text)
            == "GOVUK This phone number receives replies and cannot be changed"
        )


@pytest.mark.skip(reason="feature not in use")
def test_shows_research_mode_indicator(
    client_request,
    service_one,
    mocker,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
):
    service_one["research_mode"] = True
    mocker.patch("app.service_api_client.update_service", return_value=service_one)

    page = client_request.get(
        "main.service_settings",
        service_id=SERVICE_ONE_ID,
    )

    element = page.find("span", {"id": "research-mode"})
    assert element.text == "research mode"


def test_does_not_show_research_mode_indicator(
    client_request,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
):
    page = client_request.get(
        "main.service_settings",
        service_id=SERVICE_ONE_ID,
    )

    element = page.find("span", {"id": "research-mode"})
    assert not element


@pytest.mark.parametrize("method", ["get", "post"])
def test_cant_set_letter_contact_block_if_service_cant_send_letters(
    client_request,
    service_one,
    method,
):
    assert "letter" not in service_one["permissions"]
    getattr(client_request, method)(
        "main.service_set_letter_contact_block",
        service_id=SERVICE_ONE_ID,
        _expected_status=403,
    )


def test_set_letter_contact_block_prepopulates(
    client_request,
    service_one,
):
    service_one["permissions"] = ["letter"]
    service_one["letter_contact_block"] = "foo bar baz waz"
    page = client_request.get(
        "main.service_set_letter_contact_block",
        service_id=SERVICE_ONE_ID,
    )
    assert "foo bar baz waz" in page.text


def test_set_letter_contact_block_saves(
    client_request,
    service_one,
    mock_update_service,
):
    service_one["permissions"] = ["letter"]
    client_request.post(
        "main.service_set_letter_contact_block",
        service_id=SERVICE_ONE_ID,
        _data={"letter_contact_block": "foo bar baz waz"},
        _expected_status=302,
        _expected_redirect=url_for(
            "main.service_settings",
            service_id=SERVICE_ONE_ID,
        ),
    )
    mock_update_service.assert_called_once_with(SERVICE_ONE_ID, letter_contact_block="foo bar baz waz")


def test_set_letter_contact_block_redirects_to_template(
    client_request,
    service_one,
    mock_update_service,
):
    service_one["permissions"] = ["letter"]
    client_request.post(
        "main.service_set_letter_contact_block",
        service_id=SERVICE_ONE_ID,
        from_template=FAKE_TEMPLATE_ID,
        _data={"letter_contact_block": "23 Whitechapel Road"},
        _expected_status=302,
        _expected_redirect=url_for(
            "main.view_template",
            service_id=service_one["id"],
            template_id=FAKE_TEMPLATE_ID,
        ),
    )


def test_set_letter_contact_block_has_max_10_lines(
    client_request,
    service_one,
    mock_update_service,
):
    service_one["permissions"] = ["letter"]
    page = client_request.post(
        "main.service_set_letter_contact_block",
        service_id=SERVICE_ONE_ID,
        _data={"letter_contact_block": "\n".join(map(str, range(0, 11)))},
        _expected_status=200,
    )
    error_message = page.find("span", class_="error-message").text.strip()
    assert error_message == "Contains 11 lines, maximum is 10"


def test_request_letter_branding_if_already_have_branding(
    client_request,
    mock_get_letter_branding_by_id,
    service_one,
):
    service_one["letter_branding"] = uuid4()

    request_page = client_request.get(
        "main.request_letter_branding",
        service_id=SERVICE_ONE_ID,
    )

    mock_get_letter_branding_by_id.assert_called_once_with(service_one["letter_branding"])
    assert request_page.select_one("main p").text.strip() == "Your letters have the HM Government logo."


@pytest.mark.parametrize(
    "endpoint",
    (
        ("main.service_sms_senders"),
        ("main.service_add_sms_sender"),
    ),
)
def test_service_sms_sender_platform_admin_only(
    client_request,
    endpoint,
):
    client_request.get(
        endpoint,
        service_id=SERVICE_ONE_ID,
        _expected_status=403,
    )


def test_service_set_letter_branding_platform_admin_only(
    client_request,
):
    client_request.get(
        "main.service_set_letter_branding",
        service_id=SERVICE_ONE_ID,
        _expected_status=403,
    )


@pytest.mark.skip(reason="feature not in use")
@pytest.mark.parametrize(
    "selected_letter_branding, expected_post_data",
    [
        (str(UUID(int=1)), str(UUID(int=1))),
        ("__NONE__", None),
    ],
)
@pytest.mark.parametrize(
    "endpoint, extra_args, expected_redirect",
    (
        (
            "main.service_set_letter_branding",
            {"service_id": SERVICE_ONE_ID},
            "main.service_preview_letter_branding",
        ),
        (
            "main.edit_organisation_letter_branding",
            {"org_id": ORGANISATION_ID},
            "main.organisation_preview_letter_branding",
        ),
    ),
)
@pytest.mark.skip(reason="feature not in use")
def test_service_set_letter_branding_redirects_to_preview_page_when_form_submitted(
    client_request,
    platform_admin_user,
    mock_get_organisation,
    mock_get_all_letter_branding,
    selected_letter_branding,
    expected_post_data,
    endpoint,
    extra_args,
    expected_redirect,
):
    client_request.login(platform_admin_user)
    client_request.post(
        endpoint,
        _data={"branding_style": selected_letter_branding},
        _expected_status=302,
        _expected_redirect=url_for(
            expected_redirect,
            branding_style=expected_post_data,
            **extra_args,
        ),
        **extra_args,
    )


@pytest.mark.skip(reason="feature not in use")
@pytest.mark.parametrize(
    "endpoint, extra_args",
    (
        (
            "main.service_preview_letter_branding",
            {"service_id": SERVICE_ONE_ID},
        ),
        (
            "main.organisation_preview_letter_branding",
            {"org_id": ORGANISATION_ID},
        ),
    ),
)
def test_service_preview_letter_branding_shows_preview_letter(
    client_request,
    platform_admin_user,
    mock_get_organisation,
    mock_get_all_letter_branding,
    endpoint,
    extra_args,
):
    client_request.login(platform_admin_user)

    page = client_request.get(endpoint, branding_style="hm-government", **extra_args)

    assert page.find("iframe")["src"] == url_for("main.letter_template", branding_style="hm-government")


@pytest.mark.skip(reason="feature not in use")
@pytest.mark.parametrize(
    "selected_letter_branding, expected_post_data",
    [
        (str(UUID(int=1)), str(UUID(int=1))),
        ("__NONE__", None),
    ],
)
@pytest.mark.parametrize(
    "endpoint, extra_args, expected_redirect",
    (
        (
            "main.service_preview_letter_branding",
            {"service_id": SERVICE_ONE_ID},
            "main.service_settings",
        ),
        (
            "main.organisation_preview_letter_branding",
            {"org_id": ORGANISATION_ID},
            "main.organisation_settings",
        ),
    ),
)
def test_service_preview_letter_branding_saves(
    client_request,
    platform_admin_user,
    mock_get_organisation,
    mock_update_service,
    mock_update_organisation,
    mock_get_all_letter_branding,
    selected_letter_branding,
    expected_post_data,
    endpoint,
    extra_args,
    expected_redirect,
):
    client_request.login(platform_admin_user)
    client_request.post(
        endpoint,
        _data={"branding_style": selected_letter_branding},
        _expected_status=302,
        _expected_redirect=url_for(expected_redirect, **extra_args),
        **extra_args,
    )

    if endpoint == "main.service_preview_letter_branding":
        mock_update_service.assert_called_once_with(
            SERVICE_ONE_ID,
            letter_branding=expected_post_data,
        )
        assert mock_update_organisation.called is False

    elif endpoint == "main.organisation_preview_letter_branding":
        mock_update_organisation.assert_called_once_with(
            ORGANISATION_ID,
            letter_branding_id=expected_post_data,
        )
        assert mock_update_service.called is False

    else:
        raise Exception


@pytest.mark.parametrize(
    "current_branding, expected_values, expected_labels",
    [
        (
            "__FIP-EN__",
            [
                "__FIP-EN__",
                "__FIP-FR__",
                "1",
                "2",
                "3",
                "4",
                "5",
            ],
            [
                "English Government of Canada signature",
                "French Government of Canada signature",
                "org 1",
                "org 2",
                "org 3",
                "org 4",
                "org 5",
                "Organisation name",
            ],
        ),
        (
            "5",
            [
                "5",
                "__FIP-EN__",
                "__FIP-FR__",
                "1",
                "2",
                "3",
                "4",
            ],
            [
                "org 5",
                "English Government of Canada signature",
                "French Government of Canada signature",
                "org 1",
                "org 2",
                "org 3",
                "org 4",
                "Organisation name",
            ],
        ),
    ],
)
@pytest.mark.parametrize(
    "endpoint, extra_args, organisation_id",
    (
        (
            "main.service_set_email_branding",
            {"service_id": SERVICE_ONE_ID},
            None,
        ),
        (
            "main.edit_organisation_email_branding",
            {"org_id": ORGANISATION_ID},
            ORGANISATION_ID,
        ),
    ),
)
def test_should_show_branding_styles(
    mocker,
    client_request,
    platform_admin_user,
    service_one,
    mock_get_all_email_branding,
    mock_get_email_branding,
    app_,
    current_branding,
    expected_values,
    expected_labels,
    endpoint,
    extra_args,
    organisation_id,
):
    service_one["email_branding"] = current_branding
    mocker.patch(
        "app.organisations_client.get_organisation",
        side_effect=lambda org_id: organisation_json(
            org_id,
            "Org 1",
            email_branding_id=current_branding,
        ),
    )

    client_request.login(platform_admin_user)
    page = client_request.get(endpoint, **extra_args)

    branding_style_choices = page.find_all("input", attrs={"name": "branding_style"})

    radio_labels = [
        page.find("label", attrs={"for": branding_style_choices[idx]["id"]}).get_text().strip()
        for idx, element in enumerate(branding_style_choices)
    ]
    assert len(branding_style_choices) == 8

    for index, expected_value in enumerate(expected_values):
        assert branding_style_choices[index]["value"] == expected_value

    # radios should be in alphabetical order, based on their labels
    assert radio_labels == expected_labels

    assert "checked" in branding_style_choices[0].attrs
    assert "checked" not in branding_style_choices[1].attrs
    assert "checked" not in branding_style_choices[2].attrs
    assert "checked" not in branding_style_choices[3].attrs
    assert "checked" not in branding_style_choices[4].attrs
    assert "checked" not in branding_style_choices[5].attrs
    assert "checked" not in branding_style_choices[6].attrs

    app.email_branding_client.get_all_email_branding.assert_called_once_with(organisation_id=organisation_id)
    app.email_branding_client.get_email_branding.assert_called_once_with(app_.config["NO_BRANDING_ID"])
    app.service_api_client.get_service.assert_called_once_with(service_one["id"])


@pytest.mark.parametrize(
    "endpoint, extra_args, expected_redirect, organisation_id",
    (
        (
            "main.service_set_email_branding",
            {"service_id": SERVICE_ONE_ID},
            "main.service_preview_email_branding",
            None,
        ),
        (
            "main.edit_organisation_email_branding",
            {"org_id": ORGANISATION_ID},
            "main.organisation_preview_email_branding",
            ORGANISATION_ID,
        ),
    ),
)
def test_should_send_branding_and_organisations_to_preview(
    client_request,
    platform_admin_user,
    service_one,
    mock_get_organisation,
    mock_get_all_email_branding,
    mock_get_email_branding,
    app_,
    mock_update_service,
    endpoint,
    extra_args,
    expected_redirect,
    organisation_id,
):
    client_request.login(platform_admin_user)
    client_request.post(
        endpoint,
        data={"branding_type": "custom_logo", "branding_style": "1"},
        _expected_status=302,
        _expected_location=url_for(expected_redirect, branding_style="1", **extra_args),
        **extra_args,
    )

    mock_get_all_email_branding.assert_called_once_with(organisation_id=organisation_id)
    mock_get_email_branding.assert_called_once_with(app_.config["NO_BRANDING_ID"])


@pytest.mark.parametrize(
    "endpoint, extra_args",
    (
        (
            "main.service_preview_email_branding",
            {"service_id": SERVICE_ONE_ID},
        ),
        (
            "main.organisation_preview_email_branding",
            {"org_id": ORGANISATION_ID},
        ),
    ),
)
def test_should_preview_email_branding(
    client_request,
    platform_admin_user,
    mock_get_organisation,
    endpoint,
    extra_args,
):
    client_request.login(platform_admin_user)
    page = client_request.get(endpoint, branding_type="custom_logo", branding_style="2", **extra_args)

    iframe = page.find("iframe", attrs={"class": "branding-preview"})
    iframeURLComponents = urlparse(iframe["src"])
    iframeQString = parse_qs(iframeURLComponents.query)

    assert page.find("input", attrs={"id": "branding_style"})["value"] == "2"
    assert iframeURLComponents.path == "/_email"
    assert iframeQString["branding_style"] == ["2"]


@pytest.mark.parametrize(
    "posted_value, submitted_value",
    (
        ("2", "2"),
        ("__FIP-EN__", "__FIP-EN__"),
        ("__FIP-FR__", "__FIP-FR__"),
        pytest.param("None", None, marks=pytest.mark.xfail(raises=AssertionError)),
    ),
)
@pytest.mark.parametrize(
    "endpoint, extra_args, expected_redirect",
    (
        (
            "main.service_preview_email_branding",
            {"service_id": SERVICE_ONE_ID},
            "main.service_settings",
        ),
        (
            "main.organisation_preview_email_branding",
            {"org_id": ORGANISATION_ID},
            "main.organisation_settings",
        ),
    ),
)
def test_should_set_branding_and_organisations(
    client_request,
    platform_admin_user,
    service_one,
    mock_get_organisation,
    mock_update_service,
    mock_update_organisation,
    posted_value,
    submitted_value,
    endpoint,
    extra_args,
    expected_redirect,
):
    client_request.login(platform_admin_user)
    client_request.post(
        endpoint,
        _data={"branding_style": posted_value},
        _expected_status=302,
        _expected_redirect=url_for(expected_redirect, **extra_args),
        **extra_args,
    )
    expected_french_val = False if submitted_value == "__FIP-EN__" else True
    if endpoint == "main.service_preview_email_branding":
        if submitted_value == "__FIP-EN__" or submitted_value == "__FIP-FR__":
            mock_update_service.assert_called_once_with(
                SERVICE_ONE_ID,
                default_branding_is_french=expected_french_val,
                email_branding=None,
            )
        else:
            mock_update_service.assert_called_once_with(SERVICE_ONE_ID, email_branding=submitted_value)
        assert mock_update_organisation.called is False
    elif endpoint == "main.organisation_preview_email_branding":
        if submitted_value == "__FIP-EN__" or submitted_value == "__FIP-FR__":
            mock_update_organisation.assert_called_once_with(
                ORGANISATION_ID,
                default_branding_is_french=expected_french_val,
                email_branding_id=None,
            )
        else:
            mock_update_organisation.assert_called_once_with(
                ORGANISATION_ID,
                email_branding_id=submitted_value,
            )
        assert mock_update_service.called is False
    else:
        raise Exception


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize(
    "endpoint",
    [
        "main.set_free_sms_allowance",
    ],
)
def test_organisation_type_pages_are_platform_admin_only(
    client_request,
    method,
    endpoint,
):
    getattr(client_request, method)(
        endpoint,
        service_id=SERVICE_ONE_ID,
        _expected_status=403,
        _test_page_title=False,
    )


def test_should_show_page_to_set_message_limit(
    platform_admin_client,
    app_,
):
    response = platform_admin_client.get(url_for("main.set_message_limit", service_id=SERVICE_ONE_ID))
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    assert normalize_spaces(page.select_one("label").text) == "Daily email limit"


@freeze_time("2017-04-01 11:09:00.061258")
@pytest.mark.parametrize(
    "given_limit, expected_limit",
    [
        pytest.param("2", 1, marks=pytest.mark.xfail),  # this is less than the sms daily limit so will fail
        ("1000", 1_000),
        ("10_000", 10_000),
        pytest.param("foo", "foo", marks=pytest.mark.xfail),
    ],
)
def test_should_set_message_limit(
    platform_admin_client,
    given_limit,
    expected_limit,
    mock_update_message_limit,
):
    response = platform_admin_client.post(
        url_for(
            "main.set_message_limit",
            service_id=SERVICE_ONE_ID,
        ),
        data={
            "message_limit": given_limit,
        },
    )
    assert response.status_code == 302
    assert response.location == url_for("main.service_settings", service_id=SERVICE_ONE_ID)

    mock_update_message_limit.assert_called_with(SERVICE_ONE_ID, expected_limit)


@freeze_time("2017-04-01 11:09:00.061258")
@pytest.mark.parametrize(
    "given_limit, expected_limit",
    [
        ("1", 1),
        ("1000", 1_000),
        pytest.param("10_001", 10_000, marks=pytest.mark.xfail),
        pytest.param("foo", "foo", marks=pytest.mark.xfail),
    ],
)
def test_should_set_sms_message_limit(
    platform_admin_client,
    given_limit,
    expected_limit,
    mock_update_sms_message_limit,
):
    response = platform_admin_client.post(
        url_for(
            "main.set_sms_message_limit",
            service_id=SERVICE_ONE_ID,
        ),
        data={
            "message_limit": given_limit,
        },
    )
    assert response.status_code == 302
    assert response.location == url_for("main.service_settings", service_id=SERVICE_ONE_ID)

    mock_update_sms_message_limit.assert_called_with(SERVICE_ONE_ID, expected_limit)


@pytest.mark.parametrize(
    "limit, expected_limit",
    [
        ("1", 1),
        ("1000", 1_000),
        pytest.param("10_001", 10_000, marks=pytest.mark.xfail),
        pytest.param("foo", "foo", marks=pytest.mark.xfail),
    ],
)
def test_should_set_email_annual_limit(platform_admin_client, limit, expected_limit, mock_update_email_annual_limit, app_):
    with set_config(app_, "FF_ANNUAL_LIMIT", True):
        response = platform_admin_client.post(
            url_for("main.set_email_annual_limit", service_id=SERVICE_ONE_ID),
            data={"message_limit": limit},
        )

        assert response.status_code == 302
        assert response.location == url_for("main.service_settings", service_id=SERVICE_ONE_ID)

        mock_update_email_annual_limit.assert_called_with(SERVICE_ONE_ID, expected_limit)


@pytest.mark.parametrize(
    "limit, expected_limit",
    [
        ("1", 1),
        ("1000", 1_000),
        pytest.param("10_001", 10_000, marks=pytest.mark.xfail),
        pytest.param("foo", "foo", marks=pytest.mark.xfail),
    ],
)
def test_should_set_sms_annual_limit(
    platform_admin_client,
    limit,
    expected_limit,
    mock_update_sms_annual_limit,
    app_,
):
    with set_config(app_, "FF_ANNUAL_LIMIT", True):
        response = platform_admin_client.post(
            url_for(
                "main.set_sms_annual_limit",
                service_id=SERVICE_ONE_ID,
            ),
            data={
                "message_limit": limit,
            },
        )

        assert response.status_code == 302
        assert response.location == url_for("main.service_settings", service_id=SERVICE_ONE_ID)

        mock_update_sms_annual_limit.assert_called_with(SERVICE_ONE_ID, expected_limit)


def test_should_show_page_to_set_sms_allowance(platform_admin_client, mock_get_free_sms_fragment_limit):
    response = platform_admin_client.get(url_for("main.set_free_sms_allowance", service_id=SERVICE_ONE_ID))
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    assert normalize_spaces(page.select_one("label").text) == "Numbers of text messages per fiscal year"
    mock_get_free_sms_fragment_limit.assert_called_once_with(SERVICE_ONE_ID)


@freeze_time("2017-04-01 11:09:00.061258")
@pytest.mark.parametrize(
    "given_allowance, expected_api_argument",
    [
        ("1", 1),
        ("10_000", 10_000),
        pytest.param("foo", "foo", marks=pytest.mark.xfail),
    ],
)
def test_should_set_sms_allowance(
    platform_admin_client,
    given_allowance,
    expected_api_argument,
    mock_get_free_sms_fragment_limit,
    mock_create_or_update_free_sms_fragment_limit,
):
    response = platform_admin_client.post(
        url_for(
            "main.set_free_sms_allowance",
            service_id=SERVICE_ONE_ID,
        ),
        data={
            "free_sms_allowance": given_allowance,
        },
    )
    assert response.status_code == 302
    assert response.location == url_for("main.service_settings", service_id=SERVICE_ONE_ID)

    mock_create_or_update_free_sms_fragment_limit.assert_called_with(SERVICE_ONE_ID, expected_api_argument)


def test_old_set_letters_page_redirects(
    client_request,
):
    client_request.get(
        "main.service_set_letters",
        service_id=SERVICE_ONE_ID,
        _expected_status=301,
        _expected_redirect=url_for(
            "main.service_set_channel",
            service_id=SERVICE_ONE_ID,
            channel="letter",
        ),
    )


def test_unknown_channel_404s(
    client_request,
):
    client_request.get(
        "main.service_set_channel",
        service_id=SERVICE_ONE_ID,
        channel="message-in-a-bottle",
        _expected_status=404,
    )


@pytest.mark.parametrize(
    (
        "channel,"
        "expected_first_para,"
        "expected_legend,"
        "initial_permissions,"
        "expected_initial_value,"
        "posted_value,"
        "expected_updated_permissions"
    ),
    [
        (
            "letter",
            "It costs between 30p and 76p to send a letter using Notification.",
            "Send letters",
            ["email", "sms"],
            "False",
            "True",
            ["email", "sms", "letter"],
        ),
        (
            "letter",
            "It costs between 30p and 76p to send a letter using Notification.",
            "Send letters",
            ["email", "sms", "letter"],
            "True",
            "False",
            ["email", "sms"],
        ),
        (
            "sms",
            "You can send up to 100,000 text messages per fiscal year.",
            "Send text messages",
            [],
            "False",
            "True",
            ["sms"],
        ),
        (
            "email",
            "You can send up to 20 million emails per fiscal year for free.",
            "Send emails",
            [],
            "False",
            "True",
            ["email"],
        ),
        (
            "email",
            "You can send up to 20 million emails per fiscal year for free.",
            "Send emails",
            ["email", "sms", "letter"],
            "True",
            "True",
            ["email", "sms", "letter"],
        ),
    ],
)
def test_switch_service_enable_letters(
    client_request,
    service_one,
    mocker,
    mock_get_free_sms_fragment_limit,
    channel,
    expected_first_para,
    expected_legend,
    expected_initial_value,
    posted_value,
    initial_permissions,
    expected_updated_permissions,
):
    mocked_fn = mocker.patch("app.service_api_client.update_service", return_value=service_one)
    service_one["permissions"] = initial_permissions

    page = client_request.get(
        "main.service_set_channel",
        service_id=service_one["id"],
        channel=channel,
    )

    assert normalize_spaces(page.select_one("main p").text) == expected_first_para
    assert normalize_spaces(page.select_one("legend").text) == expected_legend

    assert page.select_one("input[checked]")["value"] == expected_initial_value
    assert len(page.select("input[checked]")) == 1

    client_request.post(
        "main.service_set_channel",
        service_id=service_one["id"],
        channel=channel,
        _data={"enabled": posted_value},
        _expected_redirect=url_for("main.service_settings", service_id=service_one["id"]),
    )

    # Ensure flash message is set
    with client_request.session_transaction() as session:
        assert session["_flashes"][0][1] == "Setting updated"

    assert set(mocked_fn.call_args[1]["permissions"]) == set(expected_updated_permissions)
    assert mocked_fn.call_args[0][0] == service_one["id"]


@pytest.mark.parametrize(
    ("initial_permissions," "expected_initial_value," "posted_value," "expected_updated_permissions"),
    [
        (
            ["email", "sms"],
            "False",
            "True",
            ["email", "sms", "upload_document"],
        ),
        (
            ["email", "sms", "upload_document"],
            "True",
            "False",
            ["email", "sms"],
        ),
    ],
)
def test_service_switch_upload_document(
    client_request,
    service_one,
    mocker,
    initial_permissions,
    expected_initial_value,
    posted_value,
    expected_updated_permissions,
):
    mocked_fn = mocker.patch("app.service_api_client.update_service", return_value=service_one)
    service_one["permissions"] = initial_permissions

    page = client_request.get(
        "main.service_switch_upload_document",
        service_id=service_one["id"],
    )

    assert page.h1.text == "Send files by email"

    paragraph = page.select_one("#main_content p").text.strip()
    assert "This feature is only available when sending through the API" in paragraph

    assert page.select_one("input[checked]")["value"] == expected_initial_value
    assert len(page.select("input[checked]")) == 1

    client_request.post(
        "main.service_switch_upload_document",
        service_id=service_one["id"],
        _data={"enabled": posted_value},
        _expected_redirect=url_for("main.service_settings", service_id=service_one["id"]),
    )
    assert set(mocked_fn.call_args[1]["permissions"]) == set(expected_updated_permissions)
    assert mocked_fn.call_args[0][0] == service_one["id"]


@pytest.mark.parametrize(
    "permissions, expected_checked",
    [
        (["international_sms"], "on"),
        ([""], "off"),
    ],
)
def test_show_international_sms_as_radio_button(
    client_request,
    service_one,
    mocker,
    permissions,
    expected_checked,
):
    service_one["permissions"] = permissions

    checked_radios = client_request.get(
        "main.service_set_international_sms",
        service_id=service_one["id"],
    ).select(".multiple-choice input[checked]")

    assert len(checked_radios) == 1
    assert checked_radios[0]["value"] == expected_checked


@pytest.mark.parametrize(
    "post_value, international_sms_permission_expected_in_api_call",
    [
        ("on", True),
        ("off", False),
    ],
)
def test_switch_service_enable_international_sms(
    client_request,
    service_one,
    mocker,
    post_value,
    international_sms_permission_expected_in_api_call,
):
    mocked_fn = mocker.patch("app.service_api_client.update_service", return_value=service_one)
    client_request.post(
        "main.service_set_international_sms",
        service_id=service_one["id"],
        _data={"enabled": post_value},
        _expected_redirect=url_for("main.service_settings", service_id=service_one["id"]),
    )

    if international_sms_permission_expected_in_api_call:
        assert "international_sms" in mocked_fn.call_args[1]["permissions"]
    else:
        assert "international_sms" not in mocked_fn.call_args[1]["permissions"]

    assert mocked_fn.call_args[0][0] == service_one["id"]


@pytest.mark.parametrize(
    "start_permissions, contact_details, end_permissions",
    [
        (["upload_document"], "http://example.com/", []),
        ([], "6502532222", ["upload_document"]),
    ],
)
@pytest.mark.skip(reason="Contact details not in use")
def test_service_switch_can_upload_document_shows_permission_page_if_service_contact_details_exist(
    platform_admin_client,
    service_one,
    mock_update_service,
    mock_get_service_settings_page_common,
    mock_get_service_organisation,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    single_sms_sender,
    start_permissions,
    contact_details,
    end_permissions,
):
    service_one["permissions"] = start_permissions
    service_one["contact_link"] = contact_details

    response = platform_admin_client.get(
        url_for("main.service_switch_can_upload_document", service_id=SERVICE_ONE_ID),
        follow_redirects=True,
    )
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    assert normalize_spaces(page.h1.text) == "Send files by email"


@pytest.mark.skip(reason="Contact details not in use")
def test_service_switch_can_upload_document_turning_permission_on_with_no_contact_details_shows_form(
    platform_admin_client,
    service_one,
    mock_get_service_settings_page_common,
    mock_get_service_organisation,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    single_sms_sender,
):
    response = platform_admin_client.get(
        url_for("main.service_switch_can_upload_document", service_id=SERVICE_ONE_ID),
        follow_redirects=True,
    )
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    assert "upload_document" not in service_one["permissions"]
    assert normalize_spaces(page.h1.text) == "Add contact details for ‘Download your document’ page"


@pytest.mark.parametrize(
    "contact_details_type, contact_details_value",
    [
        ("url", "http://example.com/"),
        ("email_address", "old@example.com"),
        ("phone_number", "6502532222"),
    ],
)
@pytest.mark.skip(reason="Contact details not in use")
def test_service_switch_can_upload_document_lets_contact_details_be_added_and_shows_permission_page(
    platform_admin_client,
    service_one,
    mock_update_service,
    mock_get_service_settings_page_common,
    mock_get_service_organisation,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    single_sms_sender,
    contact_details_type,
    contact_details_value,
):
    data = {
        "contact_details_type": contact_details_type,
        contact_details_type: contact_details_value,
    }

    response = platform_admin_client.post(
        url_for("main.service_switch_can_upload_document", service_id=SERVICE_ONE_ID),
        data=data,
        follow_redirects=True,
    )
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    assert normalize_spaces(page.h1.text) == "Send files by email"


@pytest.mark.parametrize(
    "user",
    (
        create_platform_admin_user(),
        create_active_user_with_permissions(),
        pytest.param(create_active_user_no_settings_permission(), marks=pytest.mark.xfail),
    ),
)
def test_archive_service_after_confirm(
    client_request,
    mocker,
    mock_get_organisations,
    mock_get_service_and_organisation_counts,
    mock_get_organisations_and_services_for_user,
    user,
    fake_uuid,
):
    mocked_fn = mocker.patch("app.service_api_client.post")
    client_request.login(user)
    page = client_request.post(
        "main.archive_service",
        service_id=SERVICE_ONE_ID,
        _follow_redirects=True,
    )

    mocked_fn.assert_called_once_with("/service/{}/archive".format(SERVICE_ONE_ID), data=None)
    assert normalize_spaces(page.select_one("h1").text) == "Your services"
    assert normalize_spaces(page.select_one(".banner-default-with-tick").text) == ("‘service one’ was deleted")


@pytest.mark.parametrize(
    "user",
    (
        create_platform_admin_user(),
        create_active_user_with_permissions(),
        pytest.param(create_active_user_no_settings_permission(), marks=pytest.mark.xfail),
    ),
)
def test_archive_service_prompts_user(
    client_request,
    mocker,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
    fake_uuid,
    user,
):
    mocked_fn = mocker.patch("app.service_api_client.post")
    client_request.login(user)

    settings_page = client_request.get("main.archive_service", service_id=SERVICE_ONE_ID)
    delete_link = settings_page.select(".page-footer-delete-link a")[0]
    assert normalize_spaces(delete_link.text) == "Delete this service"
    assert delete_link["href"] == url_for(
        "main.archive_service",
        service_id=SERVICE_ONE_ID,
    )

    delete_page = client_request.get(
        "main.archive_service",
        service_id=SERVICE_ONE_ID,
    )
    assert normalize_spaces(delete_page.select_one(".banner-dangerous").text) == (
        "Are you sure you want to delete ‘service one’? " "There’s no way to undo this. " "Yes, delete"
    )
    assert mocked_fn.called is False


def test_cant_archive_inactive_service(
    platform_admin_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
):
    service_one["active"] = False

    response = platform_admin_client.get(url_for("main.service_settings", service_id=service_one["id"]))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    assert "Delete service" not in {a.text for a in page.find_all("a", class_="button")}


def test_suspend_service_after_confirm(
    platform_admin_client,
    service_one,
    mocker,
    mock_get_inbound_number_for_service,
):
    mocked_fn = mocker.patch("app.service_api_client.post", return_value=service_one)

    response = platform_admin_client.post(url_for("main.suspend_service", service_id=service_one["id"]))

    assert response.status_code == 302
    assert response.location == url_for("main.service_settings", service_id=service_one["id"])
    assert mocked_fn.call_args == call("/service/{}/suspend".format(service_one["id"]), data=None)


def test_suspend_service_prompts_user(
    platform_admin_client,
    service_one,
    mocker,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
):
    mocked_fn = mocker.patch("app.service_api_client.post")

    response = platform_admin_client.get(url_for("main.suspend_service", service_id=service_one["id"]))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    assert (
        "This will suspend the service and revoke all API keys. Are you sure you want to suspend this service?"
        in page.find("div", class_="banner-dangerous").text
    )
    assert mocked_fn.called is False


def test_cant_suspend_inactive_service(
    platform_admin_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
):
    service_one["active"] = False

    response = platform_admin_client.get(url_for("main.service_settings", service_id=service_one["id"]))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    assert "Suspend service" not in {a.text for a in page.find_all("a", class_="button")}


def test_resume_service_after_confirm(
    platform_admin_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    mocker,
    mock_get_inbound_number_for_service,
):
    service_one["active"] = False
    mocked_fn = mocker.patch("app.service_api_client.post", return_value=service_one)

    response = platform_admin_client.post(url_for("main.resume_service", service_id=service_one["id"]))

    assert response.status_code == 302
    assert response.location == url_for("main.service_settings", service_id=service_one["id"])
    assert mocked_fn.call_args == call("/service/{}/resume".format(service_one["id"]), data=None)


def test_resume_service_prompts_user(
    platform_admin_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mocker,
    mock_get_service_settings_page_common,
):
    service_one["active"] = False
    mocked_fn = mocker.patch("app.service_api_client.post")

    response = platform_admin_client.get(url_for("main.resume_service", service_id=service_one["id"]))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    assert (
        "This will resume the service. New API keys are required for this service to use the API"
        in page.find("div", class_="banner-dangerous").text
    )
    assert mocked_fn.called is False


def test_cant_resume_active_service(
    platform_admin_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mock_get_service_settings_page_common,
):
    response = platform_admin_client.get(url_for("main.service_settings", service_id=service_one["id"]))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    assert "Resume service" not in {a.text for a in page.find_all("a", class_="button")}


@pytest.mark.parametrize(
    "contact_details_type, contact_details_value",
    [
        ("url", "http://example.com/"),
        ("email_address", "me@example.com"),
        ("phone_number", "6502532222"),
    ],
)
@pytest.mark.skip(reason="Contact details not in use")
def test_service_set_contact_link_prefills_the_form_with_the_existing_contact_details(
    client_request,
    service_one,
    contact_details_type,
    contact_details_value,
):
    service_one["contact_link"] = contact_details_value

    page = client_request.get("main.service_set_contact_link", service_id=SERVICE_ONE_ID)
    assert page.find("input", attrs={"name": "contact_details_type", "value": contact_details_type}).has_attr("checked")
    assert page.find("input", {"id": contact_details_type}).get("value") == contact_details_value


@pytest.mark.parametrize(
    "contact_details_type, old_value, new_value",
    [
        ("url", "http://example.com/", "http://new-link.com/"),
        ("email_address", "old@example.com", "new@example.com"),
        ("phone_number", "6502532222", "6502532223"),
    ],
)
@pytest.mark.skip(reason="Contact details not in use")
def test_service_set_contact_link_updates_contact_details_and_redirects_to_settings_page(
    client_request,
    service_one,
    mock_update_service,
    mock_get_service_settings_page_common,
    mock_get_service_organisation,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    single_sms_sender,
    contact_details_type,
    old_value,
    new_value,
):
    service_one["contact_link"] = old_value

    page = client_request.post(
        "main.service_set_contact_link",
        service_id=SERVICE_ONE_ID,
        _data={
            "contact_details_type": contact_details_type,
            contact_details_type: new_value,
        },
        _follow_redirects=True,
    )

    assert page.h1.text == "Settings"
    mock_update_service.assert_called_once_with(SERVICE_ONE_ID, contact_link=new_value)


@pytest.mark.skip(reason="Contact details not in use")
def test_service_set_contact_link_updates_contact_details_for_the_selected_field_when_multiple_textboxes_contain_data(
    client_request,
    service_one,
    mock_update_service,
    mock_get_service_settings_page_common,
    mock_get_service_organisation,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    single_sms_sender,
):
    service_one["contact_link"] = "http://www.old-url.com"

    page = client_request.post(
        "main.service_set_contact_link",
        service_id=SERVICE_ONE_ID,
        _data={
            "contact_details_type": "url",
            "url": "http://www.new-url.com",
            "email_address": "me@example.com",
            "phone_number": "6502532222",
        },
        _follow_redirects=True,
    )

    assert page.h1.text == "Settings"
    mock_update_service.assert_called_once_with(SERVICE_ONE_ID, contact_link="http://www.new-url.com")


@pytest.mark.skip(reason="Contact details not in use")
def test_service_set_contact_link_displays_error_message_when_no_radio_button_selected(client_request, service_one):
    page = client_request.post(
        "main.service_set_contact_link",
        service_id=SERVICE_ONE_ID,
        _data={
            "contact_details_type": None,
            "url": "",
            "email_address": "",
            "phone_number": "",
        },
        _follow_redirects=True,
    )
    assert normalize_spaces(page.find("span", class_="error-message").text) == "You need to choose an option"
    assert normalize_spaces(page.h1.text) == "Add contact details for ‘Download your document’ page"


@pytest.mark.parametrize(
    "contact_details_type, invalid_value, error",
    [
        ("url", "invalid.com/", "Must be a valid URL"),
        ("email_address", "me@co", "Enter a valid email address"),
        ("phone_number", "abcde", "Must be a valid phone number"),
    ],
)
@pytest.mark.skip(reason="Contact details not in use")
def test_service_set_contact_link_does_not_update_invalid_contact_details(
    mocker,
    client_request,
    service_one,
    contact_details_type,
    invalid_value,
    error,
):
    service_one["contact_link"] = "http://example.com/"
    service_one["permissions"].append("upload_document")

    page = client_request.post(
        "main.service_set_contact_link",
        service_id=SERVICE_ONE_ID,
        _data={
            "contact_details_type": contact_details_type,
            contact_details_type: invalid_value,
        },
        _follow_redirects=True,
    )

    assert normalize_spaces(page.find("span", class_="error-message").text) == error
    assert normalize_spaces(page.h1.text) == "Change contact details for ‘Download your document’ page"


@pytest.mark.skip(reason="Contact details not in use")
def test_contact_link_is_displayed_with_upload_document_permission(
    client_request,
    service_one,
    mock_get_service_settings_page_common,
    mock_get_service_organisation,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    single_sms_sender,
):
    service_one["permissions"] = ["upload_document"]
    page = client_request.get(
        "main.service_settings",
        service_id=SERVICE_ONE_ID,
    )
    assert "Contact details" in page.text


@pytest.mark.skip(reason="Contact details not in use")
def test_contact_link_is_not_displayed_without_the_upload_document_permission(
    client_request,
    service_one,
    mock_get_service_settings_page_common,
    mock_get_service_organisation,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    single_sms_sender,
):
    page = client_request.get(
        "main.service_settings",
        service_id=SERVICE_ONE_ID,
    )
    assert "Contact details" not in page.text


@pytest.mark.parametrize(
    "endpoint, permissions, expected_p",
    [
        (
            "main.service_set_inbound_sms",
            ["sms"],
            ("Contact us if you want to be able to receive text messages from your users."),
        ),
        (
            "main.service_set_inbound_sms",
            ["sms", "inbound_sms"],
            ("Your service can receive text messages sent to 0781239871."),
        ),
        ("main.service_set_auth_type", [], ("Text message code")),
        (
            "main.service_set_auth_type",
            ["email_auth"],
            ("Email code or text message code"),
        ),
    ],
)
def test_invitation_pages(
    client_request,
    service_one,
    mock_get_inbound_number_for_service,
    single_sms_sender,
    endpoint,
    permissions,
    expected_p,
):
    service_one["permissions"] = permissions
    page = client_request.get(
        endpoint,
        service_id=SERVICE_ONE_ID,
    )

    assert normalize_spaces(page.select("main p")[0].text) == expected_p


def test_service_settings_when_inbound_number_is_not_set(
    client_request,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_service_organisation,
    single_sms_sender,
    mocker,
    mock_get_all_letter_branding,
    mock_get_free_sms_fragment_limit,
    mock_get_service_data_retention,
):
    mocker.patch(
        "app.inbound_number_client.get_inbound_sms_number_for_service",
        return_value={"data": {}},
    )
    client_request.get(
        "main.service_settings",
        service_id=SERVICE_ONE_ID,
    )


def test_set_inbound_sms_when_inbound_number_is_not_set(
    client_request,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    single_sms_sender,
    mocker,
    mock_get_all_letter_branding,
):
    mocker.patch(
        "app.inbound_number_client.get_inbound_sms_number_for_service",
        return_value={"data": {}},
    )
    client_request.get(
        "main.service_set_inbound_sms",
        service_id=SERVICE_ONE_ID,
    )


@pytest.mark.parametrize(
    "user, expected_paragraphs",
    [
        (
            create_active_user_with_permissions(),
            [
                "Your service can receive text messages sent to 07700900123.",
                "You can still send text messages from a sender name if you "
                "need to, but users will not be able to reply to those messages.",
                "Contact us if you want to switch this feature off.",
                "You can set up callbacks for received text messages on the API integration page.",
            ],
        ),
        (
            create_active_user_no_api_key_permission(),
            [
                "Your service can receive text messages sent to 07700900123.",
                "You can still send text messages from a sender name if you "
                "need to, but users will not be able to reply to those messages.",
                "Contact us if you want to switch this feature off.",
            ],
        ),
    ],
)
def test_set_inbound_sms_when_inbound_number_is_set(
    client_request,
    service_one,
    mocker,
    fake_uuid,
    user,
    expected_paragraphs,
):
    service_one["permissions"] = ["inbound_sms"]
    mocker.patch(
        "app.inbound_number_client.get_inbound_sms_number_for_service",
        return_value={"data": {"number": "07700900123"}},
    )
    client_request.login(user)
    page = client_request.get(
        "main.service_set_inbound_sms",
        service_id=SERVICE_ONE_ID,
    )
    paragraphs = page.select("main p")

    assert len(paragraphs) == len(expected_paragraphs)

    for index, p in enumerate(expected_paragraphs):
        assert normalize_spaces(paragraphs[index].text) == p


def test_empty_letter_contact_block_returns_error(
    client_request,
    service_one,
    mock_update_service,
):
    service_one["permissions"] = ["letter"]
    page = client_request.post(
        "main.service_set_letter_contact_block",
        service_id=SERVICE_ONE_ID,
        _data={"letter_contact_block": None},
        _expected_status=200,
    )
    error_message = page.find("span", class_="error-message").text.strip()
    assert error_message == "This cannot be empty"


def test_show_sms_prefixing_setting_page(
    client_request,
    mock_update_service,
):
    page = client_request.get("main.service_set_sms_prefix", service_id=SERVICE_ONE_ID)
    assert normalize_spaces(page.select_one("legend").text) == ("Start all text messages with ‘service one:’")
    radios = page.select("input[type=radio]")
    assert len(radios) == 2
    assert radios[0]["value"] == "on"
    assert radios[0]["checked"] == ""
    assert radios[1]["value"] == "off"
    with pytest.raises(KeyError):
        assert radios[1]["checked"]


@pytest.mark.parametrize(
    "post_value, expected_api_argument",
    [
        ("on", True),
        ("off", False),
    ],
)
def test_updates_sms_prefixing(
    client_request,
    mock_update_service,
    post_value,
    expected_api_argument,
):
    client_request.post(
        "main.service_set_sms_prefix",
        service_id=SERVICE_ONE_ID,
        _data={"enabled": post_value},
        _expected_redirect=url_for("main.service_settings", service_id=SERVICE_ONE_ID),
    )
    mock_update_service.assert_called_once_with(
        SERVICE_ONE_ID,
        prefix_sms=expected_api_argument,
    )


def test_select_organisation(
    platform_admin_client,
    service_one,
    mock_get_service_organisation,
    mock_get_organisations,
):
    response = platform_admin_client.get(
        url_for(".link_service_to_organisation", service_id=service_one["id"]),
    )

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    assert len(page.select(".multiple-choice")) == 3
    for i in range(0, 3):
        assert normalize_spaces(page.select(".multiple-choice label")[i].text) == "Org {}".format(i + 1)


def test_select_organisation_shows_message_if_no_orgs(platform_admin_client, service_one, mock_get_service_organisation, mocker):
    mocker.patch("app.organisations_client.get_organisations", return_value=[])

    response = platform_admin_client.get(
        url_for(".link_service_to_organisation", service_id=service_one["id"]),
    )

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    assert normalize_spaces(page.select_one("main p").text) == "No organisations"
    assert not page.select_one("main button")


def test_update_service_organisation(
    platform_admin_client,
    service_one,
    mock_get_service_organisation,
    mock_get_organisations,
    mock_update_service_organisation,
):
    response = platform_admin_client.post(
        url_for(".link_service_to_organisation", service_id=service_one["id"]),
        data={"organisations": "7aa5d4e9-4385-4488-a489-07812ba13384"},
    )

    assert response.status_code == 302
    mock_update_service_organisation.assert_called_once_with(service_one["id"], "7aa5d4e9-4385-4488-a489-07812ba13384")


def test_update_service_organisation_does_not_update_if_same_value(
    platform_admin_client,
    service_one,
    mock_get_service_organisation,
    mock_get_organisations,
    mock_update_service_organisation,
):
    response = platform_admin_client.post(
        url_for(".link_service_to_organisation", service_id=service_one["id"]),
        data={"organisations": "7aa5d4e9-4385-4488-a489-07812ba13383"},
    )

    assert response.status_code == 302
    mock_update_service_organisation.called is False


@pytest.mark.skip(reason="feature not in use")
def test_show_email_branding_request_page_when_no_email_branding_is_set(client_request, mock_get_email_branding):
    page = client_request.get(".branding_request", service_id=SERVICE_ONE_ID)

    mock_get_email_branding.assert_not_called()

    radios = page.select("input[type=radio]")

    for index, option in enumerate(
        (
            "fip_english",
            "fip_french",
            "both_english",
            "both_french",
            "custom_logo",
            "custom_logo_with_background_colour",
        )
    ):
        assert radios[index]["name"] == "options"
        assert radios[index]["value"] == option


@pytest.mark.skip(reason="feature not in use")
def test_show_email_branding_request_page_when_email_branding_is_set(
    client_request,
    mock_get_email_branding,
    active_user_with_permissions,
):
    service_one = service_json(email_branding="1234")
    client_request.login(active_user_with_permissions, service=service_one)

    page = client_request.get(".branding_request", service_id=SERVICE_ONE_ID)

    mock_get_email_branding.called_once_with("1234")

    radios = page.select("input[type=radio]")

    for index, option in enumerate(
        (
            "fip_english",
            "fip_french",
            "both_english",
            "both_french",
            "custom_logo",
            "custom_logo_with_background_colour",
        )
    ):
        assert radios[index]["name"] == "options"
        assert radios[index]["value"] == option
        if option == "custom_logo":
            assert "checked" in radios[index].attrs


@pytest.mark.parametrize(
    "choice, requested_branding",
    (
        ("fip_english", "Government of Canada signature English first"),
        ("fip_french", "Government of Canada signature French first"),
        ("both_english", "Government of Canada signature English and your logo"),
        ("both_french", "Government of Canada signature French and your logo"),
        ("custom_logo", "Your logo"),
        ("custom_logo_with_background_colour", "Your logo on a colour"),
        pytest.param("foo", "Nope", marks=pytest.mark.xfail(raises=AssertionError)),
    ),
)
@pytest.mark.parametrize(
    "org_name, expected_organisation",
    (
        (None, "Can’t tell (domain is user.canada.ca)"),
        ("Test Organisation", "Test Organisation"),
    ),
)
@pytest.mark.skip(reason="feature not in use")
def test_submit_email_branding_request(
    client_request,
    mocker,
    choice,
    requested_branding,
    mock_get_service_settings_page_common,
    no_reply_to_email_addresses,
    no_letter_contact_blocks,
    single_sms_sender,
    org_name,
    expected_organisation,
):
    mock_get_service_organisation(
        mocker,
        name=org_name,
    )

    zendesk = mocker.patch(
        "app.main.views.service_settings.zendesk_client.create_ticket",
        autospec=True,
    )

    page = client_request.post(
        ".branding_request",
        service_id=SERVICE_ONE_ID,
        _data={
            "options": choice,
        },
        _follow_redirects=True,
    )

    zendesk.assert_called_once_with(
        message="\n".join(
            [
                "Organisation: {}",
                "Service: service one",
                "http://localhost/services/596364a0-858e-42c8-9062-a8fe822260eb",
                "",
                "---",
                "Current branding: default",
                "Branding requested: {}",
            ]
        ).format(expected_organisation, requested_branding),
        subject="Email branding request - service one",
        ticket_type="question",
        user_email="test@user.canada.ca",
        user_name="Test User",
        tags=["notify_action_add_branding"],
    )
    assert normalize_spaces(page.select_one(".banner-default").text) == (
        "Thanks for your branding request. We’ll get back to you " "within one working day."
    )


def test_show_service_data_retention(
    platform_admin_client,
    service_one,
    mock_get_service_data_retention,
):
    mock_get_service_data_retention.return_value[0]["days_of_retention"] = 5

    response = platform_admin_client.get(url_for("main.data_retention", service_id=service_one["id"]))
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    rows = page.select("tbody tr")
    assert len(rows) == 1
    assert normalize_spaces(rows[0].text) == "Email 5 Change"


def test_view_add_service_data_retention(
    platform_admin_client,
    service_one,
):
    response = platform_admin_client.get(url_for("main.add_data_retention", service_id=service_one["id"]))
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    assert normalize_spaces(page.select_one("input")["value"]) == "email"
    assert page.find("input", attrs={"name": "days_of_retention"})


def test_add_service_data_retention(platform_admin_client, service_one, mock_create_service_data_retention):
    response = platform_admin_client.post(
        url_for("main.add_data_retention", service_id=service_one["id"]),
        data={"notification_type": "email", "days_of_retention": 5},
    )
    assert response.status_code == 302
    settings_url = url_for("main.data_retention", service_id=service_one["id"])
    assert settings_url == response.location
    assert mock_create_service_data_retention.called


def test_update_service_data_retention(
    platform_admin_client,
    service_one,
    fake_uuid,
    mock_get_service_data_retention,
    mock_update_service_data_retention,
):
    response = platform_admin_client.post(
        url_for(
            "main.edit_data_retention",
            service_id=service_one["id"],
            data_retention_id=str(fake_uuid),
        ),
        data={"days_of_retention": 5},
    )
    assert response.status_code == 302
    settings_url = url_for("main.data_retention", service_id=service_one["id"])
    assert settings_url == response.location
    assert mock_update_service_data_retention.called


def test_update_service_data_retention_return_validation_error_for_negative_days_of_retention(
    platform_admin_client,
    service_one,
    fake_uuid,
    mock_get_service_data_retention,
    mock_update_service_data_retention,
):
    response = platform_admin_client.post(
        url_for(
            "main.edit_data_retention",
            service_id=service_one["id"],
            data_retention_id=fake_uuid,
        ),
        data={"days_of_retention": -5},
    )
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    error_message = page.find("span", class_="error-message").text.strip()
    assert error_message == "Must be between 3 and 7"
    assert mock_get_service_data_retention.called
    assert not mock_update_service_data_retention.called


def test_update_service_data_retention_populates_form(
    platform_admin_client,
    service_one,
    fake_uuid,
    mock_get_service_data_retention,
):
    mock_get_service_data_retention.return_value[0]["days_of_retention"] = 5
    response = platform_admin_client.get(
        url_for(
            "main.edit_data_retention",
            service_id=service_one["id"],
            data_retention_id=fake_uuid,
        )
    )
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
    assert page.find("input", attrs={"name": "days_of_retention"})["value"] == "5"


class TestSettingSensitiveService:
    def test_should_redirect_after_change_service_name(
        self,
        client_request,
        mock_update_service,
        service_one,
        platform_admin_user,
    ):
        client_request.login(platform_admin_user, service_one)
        client_request.post(
            "main.set_sensitive_service", service_id=SERVICE_ONE_ID, _data={"sensitive_service": False}, _expected_status=200
        )


class TestSuspendingCallbackApi:
    def test_should_suspend_service_callback_api(self, client_request, platform_admin_user, mocker, service_one):
        client_request.login(platform_admin_user, service_one)
        client_request.post(
            "main.suspend_callback",
            service_id=service_one["id"],
            _data={"updated_by_id": platform_admin_user["id"], "suspend_unsuspend": False},
            _expected_status=200,
        )


class TestSendingDomain:
    def test_sending_domain_page_shows_dropdown_of_verified_domains(
        self, client_request, platform_admin_user, mock_get_service_settings_page_common, mocker
    ):
        client_request.login(platform_admin_user)
        mock_get_domains = mocker.patch(
            "app.main.views.service_settings.get_verified_ses_domains", return_value=["domain1.com", "domain2.com"]
        )

        page = client_request.get("main.service_sending_domain", service_id=SERVICE_ONE_ID, _test_page_title=False)

        assert [option["value"] for option in page.select("select[name=sending_domain] option")] == ["domain1.com", "domain2.com"]

        mock_get_domains.assert_called_once()

    def test_sending_domain_page_populates_with_current_domain(
        self, client_request, platform_admin_user, mock_get_service_settings_page_common, mocker, service_one
    ):
        service_one["sending_domain"] = "domain1.com"
        mocker.patch("app.main.views.service_settings.get_verified_ses_domains", return_value=["domain1.com", "domain2.com"])

        client_request.login(platform_admin_user)
        page = client_request.get("main.service_sending_domain", service_id=SERVICE_ONE_ID, _test_page_title=False)

        assert page.select_one("select[name=sending_domain] option[selected]")["value"] == "domain1.com"

    def test_sending_domain_page_updates_domain_and_redirects_when_posted(
        self, client_request, platform_admin_user, mock_get_service_settings_page_common, mocker, service_one, mock_update_service
    ):
        mocker.patch("app.main.views.service_settings.get_verified_ses_domains", return_value=["domain1.com", "domain2.com"])

        client_request.login(platform_admin_user)
        client_request.post(
            "main.service_sending_domain",
            service_id=SERVICE_ONE_ID,
            _data={"sending_domain": "domain2.com"},
            _expected_redirect=url_for(
                "main.service_settings",
                service_id=SERVICE_ONE_ID,
            ),
            _test_page_title=False,
        )

        mock_update_service.assert_called_once_with(service_one["id"], sending_domain="domain2.com")

    def test_sending_domain_page_doesnt_update_if_domain_not_in_allowed_list(
        self, client_request, platform_admin_user, mock_get_service_settings_page_common, mocker, service_one, mock_update_service
    ):
        mocker.patch("app.main.views.service_settings.get_verified_ses_domains", return_value=["domain1.com", "domain2.com"])

        client_request.login(platform_admin_user)
        page = client_request.post(
            "main.service_sending_domain",
            service_id=SERVICE_ONE_ID,
            _data={"sending_domain": "domain3.com"},
            _expected_status=200,
            _test_page_title=False,
        )

        assert mock_update_service.called is False
        assert "Not a valid choice" in page.text

    def test_sending_domain_page_404s_for_non_platform_admin(self, client_request, mock_get_service_settings_page_common, mocker):
        client_request.get("main.service_sending_domain", service_id=SERVICE_ONE_ID, _expected_status=403)
