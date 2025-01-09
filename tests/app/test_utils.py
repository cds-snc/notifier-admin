from collections import OrderedDict
from csv import DictReader
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import unquote

import pytest
from flask import current_app, request
from freezegun import freeze_time
from pytest_mock import MockerFixture

from app import format_datetime_relative
from app.utils import (
    Spreadsheet,
    documentation_url,
    email_safe,
    generate_next_dict,
    generate_notifications_csv,
    generate_previous_dict,
    get_latest_stats,
    get_letter_printing_statement,
    get_logo_cdn_domain,
    get_new_default_reply_to_address,
    get_remote_addr,
    get_template,
    get_verified_ses_domains,
    printing_today_or_tomorrow,
    report_security_finding,
)
from tests.conftest import (
    SERVICE_ONE_ID,
    create_reply_to_email_address,
    fake_uuid,
    set_config,
    template_json,
)


def _get_notifications_csv(
    row_number=1,
    recipient="foo@bar.com",
    template_name="foo",
    template_type="sms",
    job_name="bar.csv",
    status="Delivered",
    created_at="1943-04-19 12:00:00",
    rows=1,
    with_links=False,
    job_id=fake_uuid,
    created_by_name=None,
    created_by_email_address=None,
):
    def _get(
        service_id,
        page=1,
        job_id=None,
        template_type=template_type,
    ):
        links = {}
        if with_links:
            links = {
                "prev": "/service/{}/notifications?page=0".format(service_id),
                "next": "/service/{}/notifications?page=1".format(service_id),
                "last": "/service/{}/notifications?page=2".format(service_id),
            }

        data = {
            "notifications": [
                {
                    "row_number": row_number + i,
                    "to": recipient,
                    "recipient": recipient,
                    "template_name": template_name,
                    "template_type": template_type,
                    "template": {"name": template_name, "template_type": template_type},
                    "job_name": job_name,
                    "status": status,
                    "created_at": created_at,
                    "updated_at": None,
                    "created_by_name": created_by_name,
                    "created_by_email_address": created_by_email_address,
                }
                for i in range(rows)
            ],
            "total": rows,
            "page_size": 50,
            "links": links,
        }

        return data

    return _get


@pytest.fixture(scope="function")
def _get_notifications_csv_mock(mocker, api_user_active, job_id=fake_uuid):
    return mocker.patch(
        "app.notification_api_client.get_notifications_for_service",
        side_effect=_get_notifications_csv(),
    )


@pytest.mark.parametrize(
    "service_name, safe_email",
    [
        ("name with spaces", "name.with.spaces"),
        ("singleword", "singleword"),
        ("UPPER CASE", "upper.case"),
        ("Service - with dash", "service-with.dash"),
        ("lots      of spaces", "lots.of.spaces"),
        ("name.with.dots", "name.with.dots"),
        ("name-with-other-delimiters", "name-with-other-delimiters"),
        ("name_with_other_delimiters", "name_with_other_delimiters"),
        (".leading", "leading"),
        ("trailing.", "trailing"),
        ("üńïçödë wördś", "unicode.words"),
        ("foo--bar", "foo-bar"),
        ("a-_-_-_-b", "a-b"),
    ],
)
def test_email_safe_return_dot_separated_email_domain(service_name, safe_email):
    assert email_safe(service_name) == safe_email


def test_generate_previous_dict(client):
    ret = generate_previous_dict("main.view_jobs", "foo", 2, {})
    assert "page=1" in ret["url"]
    assert ret["title"] == "Previous page"
    assert ret["label"] == "page 1"


def test_generate_next_dict(client):
    ret = generate_next_dict("main.view_jobs", "foo", 2, {})
    assert "page=3" in ret["url"]
    assert ret["title"] == "Next page"
    assert ret["label"] == "page 3"


def test_generate_previous_next_dict_adds_other_url_args(client):
    ret = generate_next_dict("main.view_notifications", "foo", 2, {"message_type": "blah"})
    assert "notifications/blah" in ret["url"]


def test_can_create_spreadsheet_from_large_excel_file():
    with open(str(Path.cwd() / "tests" / "spreadsheet_files" / "excel 2007.xlsx"), "rb") as xl:
        ret = Spreadsheet.from_file(xl, filename="xl.xlsx")
    assert ret.as_csv_data


def test_can_create_spreadsheet_from_dict():
    assert Spreadsheet.from_dict(
        OrderedDict(
            foo="bar",
            name="Jane",
        )
    ).as_csv_data == ("foo,name\r\n" "bar,Jane\r\n")


def test_can_create_spreadsheet_from_dict_with_filename():
    assert Spreadsheet.from_dict({}, filename="empty.csv").as_dict["file_name"] == "empty.csv"


@pytest.mark.parametrize(
    "args, kwargs",
    (
        (
            ("hello", ["hello"]),
            {},
        ),
        ((), {"csv_data": "hello", "rows": ["hello"]}),
    ),
)
def test_spreadsheet_checks_for_bad_arguments(args, kwargs):
    with pytest.raises(TypeError) as exception:
        Spreadsheet(*args, **kwargs)
    assert str(exception.value) == "Spreadsheet must be created from either rows or CSV data"


@pytest.mark.parametrize(
    "created_by_name, expected_content",
    [
        (
            None,
            [
                "Recipient,Template,Type,Sent by,Sent by email,Job,Status,Sent Time\n",
                "foo@bar.com,foo,sms,,sender@email.canada.ca,,Delivered,1943-04-19 12:00:00\r\n",
            ],
        ),
        (
            "Anne Example",
            [
                "Recipient,Template,Type,Sent by,Sent by email,Job,Status,Sent Time\n",
                "foo@bar.com,foo,sms,Anne Example,sender@email.canada.ca,,Delivered,1943-04-19 12:00:00\r\n",
            ],
        ),
    ],
)
def test_generate_notifications_csv_without_job(
    app_,
    mocker,
    created_by_name,
    expected_content,
):
    with app_.test_request_context():
        mocker.patch.dict("app.current_app.config", values={"LANGUAGES": ["en", "fr"]})
        mocker.patch(
            "app.notification_api_client.get_notifications_for_service",
            side_effect=_get_notifications_csv(
                created_by_name=created_by_name,
                created_by_email_address="sender@email.canada.ca",
                job_id=None,
                job_name=None,
            ),
        )
        assert list(generate_notifications_csv(service_id=fake_uuid))[1::] == expected_content


@pytest.mark.parametrize(
    "original_file_contents, expected_column_headers, expected_1st_row",
    [
        (
            """
            phone_number
            07700900123
        """,
            ["Row number", "Phone number", "Template", "Type", "Job", "Status", "Sent Time"],
            [
                "1",
                "07700900123",
                "foo",
                "sms",
                "bar.csv",
                "Delivered",
                "1943-04-19 12:00:00",
            ],
        ),
        (
            """
            phone_number, a, b, c
            07700900123,  🐜,🐝,🦀
            """,
            [
                "Row number",
                "Phone number",
                "a",
                "b",
                "c",
                "Template",
                "Type",
                "Job",
                "Status",
                "Sent Time",
            ],
            [
                "1",
                "07700900123",
                "🐜",
                "🐝",
                "🦀",
                "foo",
                "sms",
                "bar.csv",
                "Delivered",
                "1943-04-19 12:00:00",
            ],
        ),
        (
            """
            "phone_number", "a", "b", "c"
            "07700900123","🐜,🐜","🐝,🐝","🦀"
        """,
            [
                "Row number",
                "Phone number",
                "a",
                "b",
                "c",
                "Template",
                "Type",
                "Job",
                "Status",
                "Sent Time",
            ],
            [
                "1",
                "07700900123",
                "🐜,🐜",
                "🐝,🐝",
                "🦀",
                "foo",
                "sms",
                "bar.csv",
                "Delivered",
                "1943-04-19 12:00:00",
            ],
        ),
    ],
)
def test_generate_notifications_csv_returns_correct_csv_file(
    app_,
    mocker,
    _get_notifications_csv_mock,
    original_file_contents,
    expected_column_headers,
    expected_1st_row,
):
    with app_.test_request_context():
        mocker.patch.dict("app.current_app.config", values={"LANGUAGES": ["en", "fr"]})
        mocker.patch(
            "app.s3_client.s3_csv_client.s3download",
            return_value=original_file_contents,
        )
        # Remove encoded BOM bytes before parsing
        csv_content = list(generate_notifications_csv(service_id="1234", job_id=fake_uuid, template_type="sms"))[1::]
        csv_file = DictReader(StringIO("\n".join(csv_content)))
        assert csv_file.fieldnames == expected_column_headers
        assert next(csv_file) == dict(zip(expected_column_headers, expected_1st_row))


def test_generate_notifications_csv_only_calls_once_if_no_next_link(
    app_,
    mocker,
    _get_notifications_csv_mock,
):
    with app_.test_request_context():
        mocker.patch.dict("app.current_app.config", values={"LANGUAGES": ["en", "fr"]})
        list(generate_notifications_csv(service_id="1234"))

        assert _get_notifications_csv_mock.call_count == 1


@pytest.mark.parametrize("job_id", ["some", None])
def test_generate_notifications_csv_calls_twice_if_next_link(
    app_,
    mocker,
    job_id,
):
    with app_.test_request_context():
        mocker.patch.dict("app.current_app.config", values={"LANGUAGES": ["en", "fr"]})

        mocker.patch(
            "app.s3_client.s3_csv_client.s3download",
            return_value="""
                phone_number
                07700900000
                07700900001
                07700900002
                07700900003
                07700900004
                07700900005
                07700900006
                07700900007
                07700900008
                07700900009
            """,
        )

        service_id = "1234"
        response_with_links = _get_notifications_csv(rows=7, with_links=True)
        response_with_no_links = _get_notifications_csv(rows=3, row_number=8, with_links=False)

        mock_get_notifications = mocker.patch(
            "app.notification_api_client.get_notifications_for_service",
            side_effect=[
                response_with_links(service_id),
                response_with_no_links(service_id),
            ],
        )

        # Remove encoded BOM bytes before parsing
        csv_content = list(
            generate_notifications_csv(
                service_id=service_id,
                job_id=job_id or fake_uuid,
                template_type="sms",
            )
        )[1::]
        csv = list(DictReader(StringIO("\n".join(csv_content))))

        assert len(csv) == 10
        assert csv[0]["Phone number"] == "07700900000"
        assert csv[9]["Phone number"] == "07700900009"
        assert mock_get_notifications.call_count == 2
        # mock_calls[0][2] is the kwargs from first call
        assert mock_get_notifications.mock_calls[0][2]["page"] == 1
        assert mock_get_notifications.mock_calls[1][2]["page"] == 2


def test_get_cdn_domain_on_localhost(client, mocker):
    mocker.patch.dict("app.current_app.config", values={"ADMIN_BASE_URL": "http://localhost:6012"})
    domain = get_logo_cdn_domain()
    assert domain == current_app.config["ASSET_DOMAIN"]


@pytest.mark.parametrize(
    "time, human_readable_datetime",
    [
        ("2018-03-14 09:00", "14 March at 9:00am"),
        ("2018-03-14 15:00", "14 March at 3:00pm"),
        ("2018-03-15 09:00", "15 March at 9:00am"),
        ("2018-03-15 15:00", "15 March at 3:00pm"),
        ("2018-03-19 09:00", "19 March at 9:00am"),
        ("2018-03-19 15:00", "19 March at 3:00pm"),
        ("2018-03-19 23:59", "19 March at 11:59pm"),
        (
            "2018-03-20 00:00",
            "19 March at midnight",
        ),  # we specifically refer to 00:00 as belonging to the day before.
        ("2018-03-20 00:01", "yesterday at 12:01am"),
        ("2018-03-20 09:00", "yesterday at 9:00am"),
        ("2018-03-20 15:00", "yesterday at 3:00pm"),
        ("2018-03-20 23:59", "yesterday at 11:59pm"),
        (
            "2018-03-21 00:00",
            "yesterday at midnight",
        ),  # we specifically refer to 00:00 as belonging to the day before.
        ("2018-03-21 00:01", "today at 12:01am"),
        ("2018-03-21 09:00", "today at 9:00am"),
        ("2018-03-21 12:00", "today at midday"),
        ("2018-03-21 15:00", "today at 3:00pm"),
        ("2018-03-21 23:59", "today at 11:59pm"),
        (
            "2018-03-22 00:00",
            "today at midnight",
        ),  # we specifically refer to 00:00 as belonging to the day before.
        ("2018-03-22 00:01", "tomorrow at 12:01am"),
        ("2018-03-22 09:00", "tomorrow at 9:00am"),
        ("2018-03-22 15:00", "tomorrow at 3:00pm"),
        ("2018-03-22 23:59", "tomorrow at 11:59pm"),
        ("2018-03-23 00:01", "23 March at 12:01am"),
        ("2018-03-23 09:00", "23 March at 9:00am"),
        ("2018-03-23 15:00", "23 March at 3:00pm"),
    ],
)
@pytest.mark.skip(reason="Featured replaced by JS")
def test_format_datetime_relative(time, human_readable_datetime):
    with freeze_time("2018-03-21 12:00"):
        assert format_datetime_relative(time) == human_readable_datetime


@pytest.mark.parametrize(
    "utc_datetime",
    [
        "2018-08-01 23:00",
        "2018-08-01 16:29",
        "2018-11-01 00:00",
        "2018-11-01 10:00",
        "2018-11-01 17:29",
    ],
)
@pytest.mark.skip(reason="feature not in use")
def test_printing_today_or_tomorrow_returns_today(utc_datetime):
    with freeze_time(utc_datetime):
        assert printing_today_or_tomorrow() == "today"


@pytest.mark.parametrize(
    "datetime",
    [
        "2018-08-01 22:59",
        "2018-08-01 16:30",
        "2018-11-01 17:30",
        "2018-11-01 21:00",
        "2018-11-01 23:59",
    ],
)
@pytest.mark.skip(reason="feature not in use")
def test_printing_today_or_tomorrow_returns_tomorrow(datetime):
    with freeze_time(datetime):
        assert printing_today_or_tomorrow() == "tomorrow"


@pytest.mark.parametrize(
    "created_at, current_datetime",
    [
        ("2017-07-07T12:00:00+00:00", "2017-07-07 16:29:00"),  # created today, summer
        ("2017-12-12T12:00:00+00:00", "2017-12-12 17:29:00"),  # created today, winter
        (
            "2017-12-12T21:30:00+00:00",
            "2017-12-13 17:29:00",
        ),  # created after 5:30 yesterday
        (
            "2017-03-25T17:31:00+00:00",
            "2017-03-26 16:29:00",
        ),  # over clock change period on 2017-03-26
    ],
)
@pytest.mark.skip(reason="feature not in use")
def test_get_letter_printing_statement_when_letter_prints_today(created_at, current_datetime):
    with freeze_time(current_datetime):
        statement = get_letter_printing_statement("created", created_at)

    assert statement == "Printing starts today at 5:30pm"


@pytest.mark.parametrize(
    "created_at, current_datetime",
    [
        ("2017-07-07T16:31:00+00:00", "2017-07-07 22:59:00"),  # created today, summer
        ("2017-12-12T17:31:00+00:00", "2017-12-12 23:59:00"),  # created today, winter
    ],
)
@pytest.mark.skip(reason="feature not in use")
def test_get_letter_printing_statement_when_letter_prints_tomorrow(created_at, current_datetime):
    with freeze_time(current_datetime):
        statement = get_letter_printing_statement("created", created_at)

    assert statement == "Printing starts tomorrow at 5:30pm"


@pytest.mark.parametrize(
    "created_at, print_day",
    [
        ("2017-07-06T16:29:00+00:00", "yesterday"),
        ("2017-12-01T00:00:00+00:00", "on 1 December"),
        ("2017-03-26T12:00:00+00:00", "on 26 March"),
    ],
)
@freeze_time("2017-07-07 12:00:00")
@pytest.mark.skip(reason="feature not in use")
def test_get_letter_printing_statement_for_letter_that_has_been_sent(created_at, print_day):
    statement = get_letter_printing_statement("delivered", created_at)

    assert statement == "Printed {} at 5:30pm".format(print_day)


def test_report_security_finding(mocker, app_):
    boto_client = mocker.patch("app.utils.boto3")
    client = boto_client.client.return_value = mocker.Mock()
    client.get_caller_identity.return_value = {"Account": "123456789"}

    with app_.app_context():
        report_security_finding("foo", "bar", 50, 50)

    boto_client.client.assert_called_with("securityhub", region_name=current_app.config["AWS_REGION"])
    client.get_caller_identity.assert_called()
    client.batch_import_findings.assert_called()


@pytest.mark.parametrize(
    "forwarded_for, remote_addr, expected",
    [
        ("1.2.3.4, 192.168.1.30", None, "1.2.3.4"),
        ("1.2.3.4", None, "1.2.3.4"),
        (None, "1.2.3.4", "1.2.3.4"),
    ],
)
def test_get_remote_addr(app_, forwarded_for, remote_addr, expected):
    headers = {}
    if forwarded_for:
        headers["X-Forwarded-For"] = forwarded_for
    environ = {"REMOTE_ADDR": remote_addr}
    with app_.test_request_context(headers=headers, environ_base=environ):
        assert get_remote_addr(request) == expected


def test_get_latest_stats_k8s(mocker, app_):
    mocker.patch(
        "app.service_api_client.get_stats_by_month",
        return_value={
            "data": [
                ("2020-10-01", "sms", 5),
                ("2020-10-01", "email", 10),
                ("2020-09-01", "sms", 3),
            ]
        },
    )
    mocker.patch(
        "app.service_api_client.get_live_services_data",
        return_value={"data": ["service"]},
    )

    with app_.test_request_context():
        assert get_latest_stats("en") == {
            "notifications_total": 18,
            "emails_total": 10,
            "sms_total": 8,
            "live_services": 1,
            "monthly_stats": {
                "October 2020": {
                    "email": 10,
                    "sms": 5,
                    "total": 15,
                    "year_month": "2020-10",
                },
                "September 2020": {"sms": 3, "total": 3, "year_month": "2020-09"},
            },
        }


def test_get_latest_stats_lambda(mocker, app_):
    mocker.patch(
        "app.service_api_client.get_stats_by_month",
        return_value={
            "data": [
                {"month": "2020-10-01", "notification_type": "sms", "count": 5},
                {"month": "2020-10-01", "notification_type": "email", "count": 10},
                {"month": "2020-09-01", "notification_type": "sms", "count": 3},
            ]
        },
    )
    mocker.patch(
        "app.service_api_client.get_live_services_data",
        return_value={"data": ["service"]},
    )

    with app_.test_request_context():
        assert get_latest_stats("en") == {
            "notifications_total": 18,
            "emails_total": 10,
            "sms_total": 8,
            "live_services": 1,
            "monthly_stats": {
                "October 2020": {
                    "email": 10,
                    "sms": 5,
                    "total": 15,
                    "year_month": "2020-10",
                },
                "September 2020": {"sms": 3, "total": 3, "year_month": "2020-09"},
            },
        }


@pytest.mark.parametrize(
    "feature, lang, section, expected",
    [
        ("send", "en", None, "https://documentation.localhost:6012/en/send.html"),
        (
            "send",
            "en",
            "sending-a-file-by-email",
            "https://documentation.localhost:6012/en/send.html#sending-a-file-by-email",
        ),
        ("send", "fr", None, "https://documentation.localhost:6012/fr/envoyer.html"),
        (
            "callbacks",
            "en",
            None,
            "https://documentation.localhost:6012/en/callbacks.html",
        ),
        (
            "callbacks",
            "fr",
            None,
            "https://documentation.localhost:6012/fr/rappel.html",
        ),
        (
            "architecture",
            "en",
            None,
            "https://documentation.localhost:6012/en/architecture.html",
        ),
        (
            "architecture",
            "fr",
            None,
            "https://documentation.localhost:6012/fr/architecture.html",
        ),
        (None, "en", None, "https://documentation.localhost:6012/en/"),
        (None, "fr", None, "https://documentation.localhost:6012/fr/"),
    ],
)
def test_documentation_url(mocker, app_, feature, lang, section, expected):
    with app_.test_request_context():
        mocker.patch("app.get_current_locale", return_value=lang)
        assert documentation_url(feature, section) == expected


@pytest.mark.parametrize(
    "allowed_service_id, allow_html",
    [
        (SERVICE_ONE_ID, True),
        ("", False),
    ],
)
def test_get_template_with_html_allowed(mocker, app_, service_one, fake_uuid, allowed_service_id, allow_html):
    template = template_json(SERVICE_ONE_ID, fake_uuid, type_="email")

    with app_.test_request_context():
        with set_config(app_, "ALLOW_HTML_SERVICE_IDS", allowed_service_id):
            email_template = get_template(template, service_one)

    assert email_template is not None
    assert email_template.allow_html is allow_html


def test_set_lang_bad_route(
    client_request,
    mock_GCA_404,
):
    # test an invalid route redirects correctly
    # The args in are in a dictionary because "from" is a reserved word :/
    page = client_request.get(
        **{"endpoint": "main.set_lang", "from": "/whatever", "_expected_status": 404, "_follow_redirects": True}
    )
    assert page.select_one("h1").text.strip() == "Page could not be found"


def test_set_lang_bad_route_with_control_characters(
    client_request,
    mock_GCA_404,
):
    # test an invalid route redirects correctly
    # The args in are in a dictionary because "from" is a reserved word :/
    page = client_request.get(
        **{
            "endpoint": "main.set_lang",
            "from": unquote("%2fservice-level-agreement7gknx%00%0a0l7u2"),
            "_expected_status": 404,
            "_follow_redirects": True,
        }
    )
    assert page.select_one("h1").text.strip() == "Page could not be found"


def test_set_lang_good_route(client_request):
    page = client_request.get(
        **{"endpoint": "main.set_lang", "from": "/welcome", "_expected_status": 200, "_follow_redirects": True}
    )
    assert page.select_one("h1").text.strip() == "Welcome to GC Notify"


def test_set_lang_external_route(client_request):
    # test an external route route redirects correctly
    page = client_request.get(
        **{
            "endpoint": "main.set_lang",
            "from": "https://malicious.hacker.com",
            "_expected_status": 302,
            "_follow_redirects": False,
        }
    )
    assert len(page.findAll(text="/accounts-or-dashboard")) == 1


def test_get_new_default_reply_to_address_returns_next_in_list(mocker: MockerFixture, app_, service_one):
    reply_to_1 = create_reply_to_email_address(service_id=service_one["id"], email_address="test_1@example.com", is_default=True)
    reply_to_2 = create_reply_to_email_address(service_id=service_one["id"], email_address="test_2@example.com", is_default=False)
    reply_to_3 = create_reply_to_email_address(service_id=service_one["id"], email_address="test_3@example.com", is_default=False)
    reply_to_4 = create_reply_to_email_address(service_id=service_one["id"], email_address="test_4@example.com", is_default=False)
    email_reply_tos = [reply_to_1, reply_to_2, reply_to_3, reply_to_4]

    new_default = get_new_default_reply_to_address(email_reply_tos, reply_to_1)  # type: ignore
    assert reply_to_2 == new_default


def test_get_new_default_reply_to_address_returns_none_if_reply_to_have_(mocker: MockerFixture, app_, service_one):
    "this should never happen"
    reply_to_1 = create_reply_to_email_address(service_id=service_one["id"], email_address="test@example.com", is_default=True)
    reply_to_2 = create_reply_to_email_address(service_id=service_one["id"], email_address="test@example.com", is_default=False)
    email_reply_tos = [reply_to_1, reply_to_2]

    new_default = get_new_default_reply_to_address(email_reply_tos, reply_to_1)  # type: ignore
    assert new_default is None


def test_get_new_default_reply_to_address_returns_none_if_one_reply_to(mocker: MockerFixture, app_, service_one):
    reply_to_1 = create_reply_to_email_address(service_id=service_one["id"], email_address="test_1@example.com", is_default=True)
    email_reply_tos = [reply_to_1]

    new_default = get_new_default_reply_to_address(email_reply_tos, reply_to_1)  # type: ignore
    assert new_default is None


class TestGetSESDomains:
    @pytest.fixture
    def mock_ses_client(self):
        with patch("boto3.client") as mock_client:
            mock_ses = Mock()
            mock_client.return_value = mock_ses
            yield mock_ses

    @pytest.fixture(autouse=True)
    def mock_cache_decorator(self):
        with patch("app.utils.cache.memoize", lambda *args, **kwargs: lambda f: f):
            yield

    def test_get_verified_ses_domains(self, app_, mock_ses_client):
        # Setup mock return values
        mock_ses_client.list_identities.return_value = {"Identities": ["domain1.com", "domain2.com", "domain3.com"]}

        mock_ses_client.get_identity_verification_attributes.return_value = {
            "VerificationAttributes": {
                "domain1.com": {"VerificationStatus": "Success"},
                "domain2.com": {"VerificationStatus": "Failed"},
                "domain3.com": {"VerificationStatus": "Pending"},
            }
        }

        # Execute within app context
        with app_.test_request_context():
            result = get_verified_ses_domains()

            # Assert
            assert result == ["domain1.com"]
            mock_ses_client.list_identities.assert_called_once_with(IdentityType="Domain")
            mock_ses_client.get_identity_verification_attributes.assert_called_once_with(
                Identities=["domain1.com", "domain2.com", "domain3.com"]
            )

    def test_get_verified_ses_domains_no_domains(self, app_, mock_ses_client):
        # Setup empty response
        mock_ses_client.list_identities.return_value = {"Identities": []}
        mock_ses_client.get_identity_verification_attributes.return_value = {"VerificationAttributes": {}}

        # Execute within app context
        with app_.test_request_context():
            result = get_verified_ses_domains()

            # Assert
            assert result == []
