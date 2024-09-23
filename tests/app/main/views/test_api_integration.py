import datetime
import uuid
from collections import OrderedDict
from unittest.mock import Mock, call

import pytest
from bs4 import BeautifulSoup
from flask import url_for

from app.utils import documentation_url
from tests import sample_uuid, validate_route_permission
from tests.conftest import SERVICE_ONE_ID, create_notifications, normalize_spaces


def test_should_show_api_page(
    client_request,
    mock_login,
    api_user_active,
    mock_get_service,
    mock_has_permissions,
    mock_get_api_notifications,
):
    page = client_request.get(
        "main.api_integration",
        service_id=SERVICE_ONE_ID,
    )
    assert page.h1.string.strip() == "API integration"
    rows = page.find_all("details")
    assert len(rows) == 5
    for index, row in enumerate(rows):
        assert row.find("h3").string.strip() == "6502532222"


def test_should_show_api_page_with_lots_of_notifications(
    client_request,
    mock_login,
    api_user_active,
    mock_get_service,
    mock_has_permissions,
    mock_get_api_notifications_with_previous_next,
):
    page = client_request.get(
        "main.api_integration",
        service_id=SERVICE_ONE_ID,
    )
    rows = page.find_all("div", {"class": "api-notifications-item"})
    assert " ".join(rows[len(rows) - 1].text.split()) == (
        "Only showing the first 50 messages. GC Notify deletes messages after 7 days."
    )


def test_should_show_api_page_with_no_notifications(
    client_request,
    mock_login,
    api_user_active,
    mock_get_service,
    mock_has_permissions,
    mock_get_notifications_with_no_notifications,
):
    page = client_request.get(
        "main.api_integration",
        service_id=SERVICE_ONE_ID,
    )
    rows = page.find_all("div", {"class": "api-notifications-item"})
    assert "When you send messages via the API they’ll appear here." in rows[len(rows) - 1].text.strip()


@pytest.mark.parametrize(
    "template_type, link_text",
    [
        ("sms", "View text message"),
        ("letter", "View letter"),
        ("email", "View email"),
    ],
)
def test_letter_notifications_should_have_link_to_view_letter(
    client_request,
    mock_has_permissions,
    mocker,
    template_type,
    link_text,
):
    notifications = create_notifications(template_type=template_type)
    mocker.patch("app.notification_api_client.get_api_notifications_for_service", return_value=notifications)
    page = client_request.get(
        "main.api_integration",
        service_id=SERVICE_ONE_ID,
    )

    assert page.select_one("details a").text.strip() == link_text


@pytest.mark.parametrize("status", ["pending-virus-check", "virus-scan-failed"])
def test_should_not_have_link_to_view_letter_for_precompiled_letters_in_virus_states(
    client_request, fake_uuid, mock_has_permissions, mocker, status
):
    notifications = create_notifications(status=status)
    mocker.patch("app.notification_api_client.get_api_notifications_for_service", return_value=notifications)

    page = client_request.get(
        "main.api_integration",
        service_id=fake_uuid,
    )

    assert not page.select_one("details a")


@pytest.mark.parametrize(
    "client_reference, shows_ref",
    [
        ("foo", True),
        (None, False),
    ],
)
def test_letter_notifications_should_show_client_reference(
    client_request,
    fake_uuid,
    mock_has_permissions,
    mocker,
    client_reference,
    shows_ref,
):
    notifications = create_notifications(client_reference=client_reference)
    mocker.patch("app.notification_api_client.get_api_notifications_for_service", return_value=notifications)

    page = client_request.get(
        "main.api_integration",
        service_id=fake_uuid,
    )
    dt_arr = [p.text for p in page.select("dt")]

    if shows_ref:
        assert "client_reference:" in dt_arr
        assert page.select_one("dd:nth-of-type(2)").text == "foo"
    else:
        assert "client_reference:" not in dt_arr


def test_should_show_api_page_for_live_service(
    client_request,
    mock_login,
    api_user_active,
    mock_get_notifications,
    mock_get_live_service,
    mock_has_permissions,
):
    page = client_request.get("main.api_integration", service_id=uuid.uuid4())
    assert "Your service is in trial mode" not in page.find("main").text


def test_api_documentation_page_should_redirect(
    client_request, mock_login, api_user_active, mock_get_service, mock_has_permissions
):
    client_request.get(
        "main.api_documentation",
        service_id=SERVICE_ONE_ID,
        _expected_status=301,
        _expected_redirect=documentation_url(),
    )


class TestApiKeys:
    def test_should_show_api_keys_page(
        self,
        client_request,
        mock_get_api_keys,
        mock_get_api_key_statistics,
    ):
        page = client_request.get("main.api_keys", service_id=SERVICE_ONE_ID)
        rows = [normalize_spaces(row.text) for row in page.select("main tr")]

        assert rows[0] == "API keys Action"
        assert "another key name 20 total sends in the last 7 days (20 email, 0 sms)" in rows[1]
        assert "Revoke API key some key name" in rows[2]

        mock_get_api_keys.assert_called_once_with(SERVICE_ONE_ID)

    def test_should_show_empty_api_keys_page(
        self,
        client,
        api_user_active,
        mock_login,
        mock_get_no_api_keys,
        mock_get_service,
        mock_has_permissions,
    ):
        client.login(api_user_active)
        service_id = str(uuid.uuid4())
        response = client.get(url_for("main.api_keys", service_id=service_id))

        assert response.status_code == 200
        assert "You have not created any API keys yet" in response.get_data(as_text=True)
        assert "Create API key" in response.get_data(as_text=True)
        mock_get_no_api_keys.assert_called_once_with(service_id)

    @pytest.mark.parametrize(
        "restricted, can_send_letters, expected_options",
        [
            (
                True,
                False,
                [
                    ("Live – sends to anyone " "Not available because your service is in trial mode."),
                    "Team and safelist – limits who you can send to",
                    "Test – pretends to send messages",
                ],
            ),
            (
                False,
                False,
                [
                    "Live – sends to anyone",
                    "Team and safelist – limits who you can send to",
                    "Test – pretends to send messages",
                ],
            ),
            (
                False,
                True,
                [
                    "Live – sends to anyone",
                    ("Team and safelist – limits who you can send to" ""),
                    "Test – pretends to send messages",
                ],
            ),
        ],
    )
    def test_should_show_create_api_key_page(
        self,
        client_request,
        mocker,
        api_user_active,
        mock_get_api_keys,
        restricted,
        can_send_letters,
        expected_options,
        service_one,
    ):
        service_one["restricted"] = restricted
        if can_send_letters:
            service_one["permissions"].append("letter")

        mocker.patch("app.service_api_client.get_service", return_value={"data": service_one})

        page = client_request.get("main.create_api_key", service_id=SERVICE_ONE_ID)

        for index, option in enumerate(expected_options):
            assert normalize_spaces(page.select(".block-label")[index].text) == option

    def test_should_create_api_key_with_type_normal(
        self,
        client_request,
        api_user_active,
        mock_login,
        mock_get_api_keys,
        mock_get_live_service,
        mock_has_permissions,
        fake_uuid,
        mocker,
    ):
        key_name_from_user = "Some default key name 1/2"
        key_name_fixed = "some_default_key_name_12"
        post = mocker.patch(
            "app.notify_client.api_key_api_client.ApiKeyApiClient.post",
            return_value={"data": {"key": fake_uuid, "key_name": key_name_fixed}},
        )

        page = client_request.post(
            "main.create_api_key",
            service_id=SERVICE_ONE_ID,
            _data={"key_name": key_name_from_user, "key_type": "normal"},
            _expected_status=200,
        )

        assert page.select_one("span.api-key-key").text.strip() == ("{}-{}-{}".format(key_name_fixed, SERVICE_ONE_ID, fake_uuid))

        post.assert_called_once_with(
            url="/service/{}/api-key".format(SERVICE_ONE_ID),
            data={
                "name": key_name_from_user,
                "key_type": "normal",
                "created_by": api_user_active["id"],
            },
        )

    def test_cant_create_normal_api_key_in_trial_mode(
        self,
        client_request,
        api_user_active,
        mock_login,
        mock_get_api_keys,
        mock_get_service,
        mock_has_permissions,
        fake_uuid,
        mocker,
    ):
        mock_post = mocker.patch("app.notify_client.api_key_api_client.ApiKeyApiClient.post")

        client_request.post(
            "main.create_api_key",
            service_id=SERVICE_ONE_ID,
            _data={"key_name": "some default key name", "key_type": "normal"},
            _expected_status=400,
        )
        mock_post.assert_not_called()

    def test_should_show_confirm_revoke_api_key(
        self,
        client_request,
        mock_get_api_keys,
        fake_uuid,
    ):
        page = client_request.get(
            "main.revoke_api_key",
            service_id=SERVICE_ONE_ID,
            key_id=fake_uuid,
            _test_page_title=False,
        )
        assert normalize_spaces(page.select(".banner-dangerous")[0].text) == (
            "Are you sure you want to revoke ‘some key name’? "
            "You will not be able to use this API key to connect to GC Notify "
            "Yes, revoke this API key"
        )
        assert mock_get_api_keys.call_args_list == [
            call("596364a0-858e-42c8-9062-a8fe822260eb"),
        ]

    def test_should_show_confirm_revoke_api_key_for_platform_admin(
        self,
        platform_admin_client,
        mock_get_api_keys,
        fake_uuid,
    ):
        url = url_for(
            "main.revoke_api_key",
            service_id=SERVICE_ONE_ID,
            key_id=fake_uuid,
            _test_page_title=False,
        )
        response = platform_admin_client.get(url)
        page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
        assert normalize_spaces(page.select(".banner-dangerous")[0].text) == (
            "Are you sure you want to revoke ‘some key name’? "
            "You will not be able to use this API key to connect to GC Notify "
            "Yes, revoke this API key"
        )
        assert mock_get_api_keys.call_args_list == [
            call("596364a0-858e-42c8-9062-a8fe822260eb"),
        ]

    def test_should_404_for_api_key_that_doesnt_exist(
        self,
        client_request,
        mock_get_api_keys,
    ):
        client_request.get(
            "main.revoke_api_key",
            service_id=SERVICE_ONE_ID,
            key_id="key-doesn’t-exist",
            _expected_status=404,
        )

    def test_should_redirect_after_revoking_api_key(
        self,
        client_request,
        api_user_active,
        mock_login,
        mock_revoke_api_key,
        mock_get_api_keys,
        mock_get_service,
        mock_has_permissions,
        fake_uuid,
    ):
        client_request.post(
            "main.revoke_api_key",
            service_id=SERVICE_ONE_ID,
            key_id=fake_uuid,
            _expected_status=302,
            _expected_redirect=url_for(
                ".api_keys",
                service_id=SERVICE_ONE_ID,
            ),
        )
        mock_revoke_api_key.assert_called_once_with(service_id=SERVICE_ONE_ID, key_id=fake_uuid)
        mock_get_api_keys.assert_called_once_with(
            SERVICE_ONE_ID,
        )

    @pytest.mark.parametrize("route", ["main.api_keys", "main.create_api_key", "main.revoke_api_key"])
    def test_route_permissions(
        self,
        mocker,
        app_,
        fake_uuid,
        api_user_active,
        service_one,
        mock_get_api_keys,
        route,
        mock_get_api_key_statistics,
    ):
        with app_.test_request_context():
            validate_route_permission(
                mocker,
                app_,
                "GET",
                200,
                url_for(route, service_id=service_one["id"], key_id=fake_uuid),
                ["manage_api_keys"],
                api_user_active,
                service_one,
            )

    @pytest.mark.parametrize("route", ["main.api_keys", "main.create_api_key", "main.revoke_api_key"])
    def test_route_invalid_permissions(
        self,
        mocker,
        app_,
        fake_uuid,
        api_user_active,
        service_one,
        mock_get_api_keys,
        route,
    ):
        with app_.test_request_context():
            validate_route_permission(
                mocker,
                app_,
                "GET",
                403,
                url_for(route, service_id=service_one["id"], key_id=fake_uuid),
                ["view_activity"],
                api_user_active,
                service_one,
            )


class TestSafelist:
    def test_should_update_safelist(
        self,
        client_request,
        mock_update_safelist,
    ):
        data = OrderedDict(
            [
                ("email_addresses-1", "test@example.com"),
                ("email_addresses-3", "test@example.com"),
                ("phone_numbers-0", "6502532222"),
                ("phone_numbers-2", "+4966921809"),
            ]
        )

        client_request.post(
            "main.safelist",
            service_id=SERVICE_ONE_ID,
            _data=data,
        )

        mock_update_safelist.assert_called_once_with(
            SERVICE_ONE_ID,
            {
                "email_addresses": ["test@example.com", "test@example.com"],
                "phone_numbers": ["6502532222", "+4966921809"],
            },
        )

    def test_should_show_safelist_page(
        self,
        client_request,
        mock_login,
        api_user_active,
        mock_get_service,
        mock_has_permissions,
        mock_get_safelist,
    ):
        page = client_request.get(
            "main.safelist",
            service_id=SERVICE_ONE_ID,
        )
        textboxes = page.find_all("input", {"type": "email"}) + page.find_all("input", {"type": "tel"})
        for index, value in enumerate(["test@example.com"] + [""] * 4 + ["6502532222"] + [""] * 4):
            assert textboxes[index]["value"] == value

    def test_should_validate_safelist_items(
        self,
        client_request,
        mock_update_safelist,
    ):
        page = client_request.post(
            "main.safelist",
            service_id=SERVICE_ONE_ID,
            _data=OrderedDict([("email_addresses-1", "abc"), ("phone_numbers-0", "123")]),
            _expected_status=200,
        )

        assert page.select_one(".banner-title").string.strip() == "There was a problem with your safelist"
        jump_links = page.select(".banner-dangerous a")

        assert jump_links[0].string.strip() == "Enter valid email addresses"
        assert jump_links[0]["href"] == "#email_addresses"

        assert jump_links[1].string.strip() == "Enter valid phone numbers"
        assert jump_links[1]["href"] == "#phone_numbers"

        assert mock_update_safelist.called is False


class TestApiCallbacks:
    @pytest.mark.parametrize(
        "endpoint",
        [
            ("main.delivery_status_callback"),
            ("main.received_text_messages_callback"),
        ],
    )
    @pytest.mark.parametrize(
        "url, bearer_token, response, expected_errors",
        [
            ("https://example.com", "", None, "This cannot be empty"),
            ("http://not_https.com", "1234567890", None, "Enter a URL that starts with https://"),
            (
                "https://test.com",
                "123456789",
                {"content": "a", "status_code": 500, "headers": {"a": "a"}},
                "Must be at least 10 characters",
            ),
            (
                "https://test.ee",
                "1234567890",
                {"content": "a", "status_code": 404, "headers": {"a": "a"}},
                "Check your service is running and not using a proxy we cannot access",
            ),
        ],
    )
    def test_callback_forms_validation(
        self,
        client_request,
        service_one,
        mock_get_valid_service_callback_api,
        mock_validate_callback_url,
        endpoint,
        url,
        bearer_token,
        response,
        expected_errors,
        mocker,
    ):
        if endpoint == "main.received_text_messages_callback":
            service_one["permissions"] = ["inbound_sms"]

        data = {
            "url": url,
            "bearer_token": bearer_token,
        }
        if response:
            resp = Mock(content=response["content"], status_code=response["status_code"], headers=response["headers"])
            mocker.patch("app.main.validators.requests.post", return_value=resp)

        response = client_request.post(endpoint, service_id=service_one["id"], _data=data, _expected_status=200)
        error_msgs = " ".join(msg.text.strip() for msg in response.select(".error-message"))

        assert error_msgs == expected_errors

    @pytest.mark.parametrize(
        "endpoint",
        [
            ("main.delivery_status_callback"),
            ("main.received_text_messages_callback"),
        ],
    )
    def test_callback_response_time_banner_shows_error_when_response_time_greater_than_one_second(
        self,
        endpoint,
        fake_uuid,
        client_request,
        service_one,
        mock_get_valid_service_callback_api,
        mock_get_valid_service_inbound_api,
        mocker,
    ):
        mocker.patch(
            "app.main.validators.requests.post", return_value=Mock(elapsed=datetime.timedelta(seconds=1.1), status_code=200)
        )

        if endpoint == "main.received_text_messages_callback":
            service_one["permissions"] = ["inbound_sms"]
            service_one["inbound_api"] = [fake_uuid]
            url = "https://hello3.canada.ca"
        else:
            service_one["service_callback_api"] = [fake_uuid]
            url = "https://hello2.canada.ca"

        data = {
            "url": url,
            "bearer_token": "bearer_token_set",
            "button_pressed": "test_response_time",
        }

        response = client_request.post(
            endpoint,
            service_id=service_one["id"],
            _data=data,
            _follow_redirects=True,
        )

        expected_banner_msg = f"The service {url.split('https://')[1]} took longer than 1 second to respond."
        page = BeautifulSoup(response.decode("utf-8"), "html.parser")
        banner_msg = normalize_spaces(page.select(".banner-dangerous")[0].text)

        assert banner_msg == expected_banner_msg

    @pytest.mark.parametrize(
        "endpoint, expected_delete_url",
        [
            (
                "main.delete_delivery_status_callback",
                "/service/{}/delivery-receipt-api/{}",
            ),
            (
                "main.delete_received_text_messages_callback",
                "/service/{}/inbound-api/{}",
            ),
        ],
    )
    def test_delete_delivery_status_and_receive_text_message_callbacks(
        self,
        client_request,
        service_one,
        endpoint,
        expected_delete_url,
        mocker,
        fake_uuid,
        mock_get_valid_service_callback_api,
        mock_get_valid_service_inbound_api,
    ):
        service_one["service_callback_api"] = [fake_uuid]
        service_one["inbound_api"] = [fake_uuid]
        service_one["permissions"] = ["inbound_sms"]
        mocked_delete = mocker.patch("app.service_api_client.delete")

        page = client_request.post(
            endpoint,
            service_id=service_one["id"],
            _follow_redirects=True,
        )

        assert not page.select(".error-message")
        mocked_delete.assert_called_once_with(expected_delete_url.format(service_one["id"], fake_uuid))

    @pytest.mark.parametrize(
        "has_inbound_sms, expected_link",
        [
            (True, "main.api_callbacks"),
            (False, "main.delivery_status_callback"),
        ],
    )
    def test_callbacks_button_links_straight_to_delivery_status_if_service_has_no_inbound_sms(
        self,
        client_request,
        service_one,
        mocker,
        mock_get_notifications,
        has_inbound_sms,
        expected_link,
    ):
        if has_inbound_sms:
            service_one["permissions"] = ["inbound_sms"]

        page = client_request.get(
            "main.api_integration",
            service_id=service_one["id"],
        )

        assert page.select(".api-header-links")[2]["href"] == url_for(expected_link, service_id=service_one["id"])

    def test_callbacks_page_redirects_to_delivery_status_if_service_has_no_inbound_sms(
        self,
        client_request,
        service_one,
        mocker,
        mock_get_valid_service_callback_api,
    ):
        page = client_request.get(
            "main.api_callbacks",
            service_id=service_one["id"],
            _follow_redirects=True,
        )

        assert normalize_spaces(page.select_one("h1").text) == "Callbacks for delivery receipts"

    @pytest.mark.parametrize(
        "has_inbound_sms, expected_link",
        [
            (True, "main.api_callbacks"),
            (False, "main.api_integration"),
        ],
    )
    def test_back_link_directs_to_api_integration_from_delivery_callback_if_no_inbound_sms(
        self, client_request, service_one, mocker, has_inbound_sms, expected_link
    ):
        if has_inbound_sms:
            service_one["permissions"] = ["inbound_sms"]

        page = client_request.get(
            "main.delivery_status_callback",
            service_id=service_one["id"],
            _follow_redirects=True,
        )

        assert page.select_one(".back-link")["href"] == url_for(expected_link, service_id=service_one["id"])

    @pytest.mark.parametrize(
        "endpoint",
        [
            ("main.delivery_status_callback"),
            ("main.received_text_messages_callback"),
        ],
    )
    def test_create_delivery_status_and_receive_text_message_callbacks(
        self,
        client_request,
        service_one,
        mocker,
        mock_get_notifications,
        mock_create_service_inbound_api,
        mock_create_service_callback_api,
        endpoint,
        fake_uuid,
        mock_validate_callback_url,
    ):
        if endpoint == "main.received_text_messages_callback":
            service_one["permissions"] = ["inbound_sms"]

        data = {
            "url": "https://test.url.com/",
            "bearer_token": "1234567890",
            "user_id": fake_uuid,
        }

        client_request.post(
            endpoint,
            service_id=service_one["id"],
            _data=data,
        )

        if endpoint == "main.received_text_messages_callback":
            mock_create_service_inbound_api.assert_called_once_with(
                service_one["id"],
                url="https://test.url.com/",
                bearer_token="1234567890",
                user_id=fake_uuid,
            )
        else:
            mock_create_service_callback_api.assert_called_once_with(
                service_one["id"],
                url="https://test.url.com/",
                bearer_token="1234567890",
                user_id=fake_uuid,
            )

    def test_update_delivery_status_callback_details(
        self,
        client_request,
        service_one,
        mock_update_service_callback_api,
        mock_get_valid_service_callback_api,
        fake_uuid,
        mock_validate_callback_url,
        mocker,
    ):
        service_one["service_callback_api"] = [fake_uuid]

        data = {
            "url": "https://test.url.com/",
            "bearer_token": "1234567890",
            "user_id": fake_uuid,
        }

        client_request.post(
            "main.delivery_status_callback",
            service_id=service_one["id"],
            _data=data,
        )

        mock_update_service_callback_api.assert_called_once_with(
            service_one["id"],
            url="https://test.url.com/",
            bearer_token="1234567890",
            user_id=fake_uuid,
            callback_api_id=fake_uuid,
        )

    def test_update_receive_text_message_callback_details(
        self,
        client_request,
        service_one,
        mock_update_service_inbound_api,
        mock_get_valid_service_inbound_api,
        fake_uuid,
        mock_validate_callback_url,
    ):
        service_one["inbound_api"] = [fake_uuid]
        service_one["permissions"] = ["inbound_sms"]

        data = {"url": "https://test.url.com/", "bearer_token": "1234567890", "user_id": fake_uuid}

        client_request.post(
            "main.received_text_messages_callback",
            service_id=service_one["id"],
            _data=data,
        )

        mock_update_service_inbound_api.assert_called_once_with(
            service_one["id"],
            url="https://test.url.com/",
            bearer_token="1234567890",
            user_id=fake_uuid,
            inbound_api_id=fake_uuid,
        )

    def test_update_delivery_status_callback_without_changes_does_not_update(
        self,
        client_request,
        service_one,
        mock_update_service_callback_api,
        fake_uuid,
        mock_get_valid_service_callback_api,
        mock_validate_callback_url,
        mocker,
    ):
        service_one["service_callback_api"] = [fake_uuid]
        data = {"user_id": fake_uuid, "url": "https://hello2.canada.ca", "bearer_token": "bearer_token_set"}

        client_request.post(
            "main.delivery_status_callback",
            service_id=service_one["id"],
            _data=data,
        )

        assert mock_update_service_callback_api.called is False

    def test_update_receive_text_message_callback_without_changes_does_not_update(
        self,
        client_request,
        service_one,
        mock_update_service_inbound_api,
        fake_uuid,
        mock_get_valid_service_inbound_api,
        mock_validate_callback_url,
    ):
        service_one["inbound_api"] = [fake_uuid]
        service_one["permissions"] = ["inbound_sms"]
        data = {"user_id": fake_uuid, "url": "https://hello3.canada.ca", "bearer_token": "bearer_token_set"}

        client_request.post(
            "main.received_text_messages_callback",
            service_id=service_one["id"],
            _data=data,
        )

        assert mock_update_service_inbound_api.called is False

    @pytest.mark.parametrize(
        "service_callback_api, delivery_url, expected_1st_table_row",
        [
            (None, {}, "Delivery receipts Not set Change"),
            (
                sample_uuid(),
                {"url": "https://delivery.receipts"},
                "Delivery receipts https://delivery.receipts Change",
            ),
        ],
    )
    @pytest.mark.parametrize(
        "inbound_api, inbound_url, expected_2nd_table_row",
        [
            (None, {}, "Received text messages Not set Change"),
            (
                sample_uuid(),
                {"url": "https://inbound.sms"},
                "Received text messages https://inbound.sms Change",
            ),
        ],
    )
    def test_callbacks_page_works_when_no_apis_set(
        self,
        client_request,
        service_one,
        mocker,
        service_callback_api,
        delivery_url,
        expected_1st_table_row,
        inbound_api,
        inbound_url,
        expected_2nd_table_row,
    ):
        service_one["permissions"] = ["inbound_sms"]
        service_one["inbound_api"] = inbound_api
        service_one["service_callback_api"] = service_callback_api

        mocker.patch("app.service_api_client.get_service_callback_api", return_value=delivery_url)
        mocker.patch("app.service_api_client.get_service_inbound_api", return_value=inbound_url)

        page = client_request.get("main.api_callbacks", service_id=service_one["id"], _follow_redirects=True)
        expected_rows = [
            expected_1st_table_row,
            expected_2nd_table_row,
        ]
        rows = page.select("tbody tr")
        assert len(rows) == 2
        for index, row in enumerate(expected_rows):
            assert row == normalize_spaces(rows[index].text)
