# -*- coding: utf-8 -*-
import sys
import uuid
from functools import partial
from glob import glob
from io import BytesIO
from itertools import repeat
from os import path
from unittest.mock import patch
from uuid import uuid4
from zipfile import BadZipFile

import pytest
from bs4 import BeautifulSoup
from flask import url_for
from notifications_python_client.errors import HTTPError
from notifications_utils.clients.redis import (
    email_daily_count_cache_key,
    sms_daily_count_cache_key,
)
from notifications_utils.recipients import RecipientCSV
from notifications_utils.template import LetterImageTemplate, LetterPreviewTemplate
from xlrd.biffh import XLRDError
from xlrd.xldate import XLDateAmbiguous, XLDateError, XLDateNegative, XLDateTooLarge

from app.main.views.send import daily_email_count, daily_sms_fragment_count
from tests import validate_route_permission, validate_route_permission_with_client
from tests.conftest import (
    SERVICE_ONE_ID,
    create_active_caseworking_user,
    create_active_user_with_permissions,
    create_email_template,
    create_letter_template,
    create_multiple_email_reply_to_addresses,
    create_multiple_sms_senders,
    create_multiple_sms_senders_no_inbound,
    create_multiple_sms_senders_with_diff_default,
    create_sms_template,
    create_template,
    fake_uuid,
    mock_get_service_email_template,
    mock_get_service_letter_template,
    mock_get_service_template,
    normalize_spaces,
    set_config,
)

template_types = ["email", "sms"]

unchanging_fake_uuid = uuid.uuid4()

# The * ignores hidden files, eg .DS_Store
test_spreadsheet_files = glob(path.join("tests", "spreadsheet_files", "*"))
test_non_spreadsheet_files = glob(path.join("tests", "non_spreadsheet_files", "*"))


@pytest.mark.parametrize("redis_value,expected_result", [(None, 0), ("3", 3)])
def test_daily_sms_fragment_count(mocker, redis_value, expected_result):
    mocker.patch(
        "app.extensions.redis_client.get", lambda x: redis_value if x == sms_daily_count_cache_key(SERVICE_ONE_ID) else None
    )
    assert daily_sms_fragment_count(SERVICE_ONE_ID) == expected_result


@pytest.mark.parametrize("redis_value,expected_result", [(None, 0), ("3", 3)])
def test_daily_email_count(mocker, redis_value, expected_result):
    mocker.patch(
        "app.extensions.redis_client.get", lambda x: redis_value if x == email_daily_count_cache_key(SERVICE_ONE_ID) else None
    )
    assert daily_email_count(SERVICE_ONE_ID) == expected_result


@pytest.mark.parametrize(
    "template_type, sender_data, expected_title, expected_description",
    [
        (
            "email",
            create_multiple_email_reply_to_addresses(),
            "Where should replies come back to?",
            "Where should replies come back to?",
        ),
        (
            "sms",
            create_multiple_sms_senders(),
            "Who should the message come from?",
            "Who should the message come from?",
        ),
    ],
)
def test_show_correct_title_and_description_for_sender_type(
    client_request,
    service_one,
    fake_uuid,
    template_type,
    sender_data,
    expected_title,
    expected_description,
    mocker,
):
    mocker.patch("app.service_api_client.get_service_template", return_value=create_template(template_type=template_type))

    mocker.patch("app.service_api_client.get_reply_to_email_addresses", return_value=sender_data)
    mocker.patch("app.service_api_client.get_sms_senders", return_value=sender_data)

    page = client_request.get(".set_sender", service_id=service_one["id"], template_id=fake_uuid)

    assert page.select_one("h1").text == expected_title
    assert normalize_spaces(page.select_one("legend .visually-hidden").text) == expected_description


@pytest.mark.parametrize(
    "template_type, sender_data",
    [
        (
            "email",
            create_multiple_email_reply_to_addresses(),
        ),
        ("sms", create_multiple_sms_senders_with_diff_default()),
        ("sms", create_multiple_sms_senders_no_inbound()),
    ],
)
def test_default_sender_is_checked_and_has_hint(client_request, service_one, fake_uuid, template_type, sender_data, mocker):
    template_data = create_template(template_type=template_type)
    mocker.patch("app.service_api_client.get_service_template", return_value=template_data)

    mocker.patch("app.service_api_client.get_sms_senders", return_value=sender_data)
    mocker.patch("app.service_api_client.get_reply_to_email_addresses", return_value=sender_data)
    page = client_request.get(".set_sender", service_id=service_one["id"], template_id=fake_uuid)

    assert page.select(".multiple-choice input")[0].has_attr("checked")
    assert normalize_spaces(page.select_one(".multiple-choice label .block-label-hint").text) == "(Default)"
    assert not page.select(".multiple-choice input")[1].has_attr("checked")


def test_default_inbound_sender_is_checked_and_has_hint_with_default_and_receives_text(
    client_request,
    service_one,
    fake_uuid,
    mock_get_service_template,
    multiple_sms_senders,
):
    page = client_request.get(".set_sender", service_id=service_one["id"], template_id=fake_uuid)

    assert page.select(".multiple-choice input")[0].has_attr("checked")
    assert normalize_spaces(page.select_one(".multiple-choice label .block-label-hint").text) == "(Default and receives replies)"
    assert not page.select(".multiple-choice input")[1].has_attr("checked")
    assert not page.select(".multiple-choice input")[2].has_attr("checked")


def test_sms_sender_has_receives_replies_hint(
    client_request,
    service_one,
    fake_uuid,
    mock_get_service_template,
    multiple_sms_senders,
):
    page = client_request.get(".set_sender", service_id=service_one["id"], template_id=fake_uuid)

    assert page.select(".multiple-choice input")[0].has_attr("checked")
    assert normalize_spaces(page.select_one(".multiple-choice label .block-label-hint").text) == "(Default and receives replies)"
    assert not page.select(".multiple-choice input")[1].has_attr("checked")
    assert not page.select(".multiple-choice input")[2].has_attr("checked")


@pytest.mark.parametrize(
    "template_type, sender_data",
    [
        (
            "email",
            create_multiple_email_reply_to_addresses(),
        ),
        ("sms", create_multiple_sms_senders()),
    ],
)
def test_sender_session_is_present_after_selected(client_request, service_one, fake_uuid, template_type, sender_data, mocker):
    template_data = create_template(template_type=template_type)
    mocker.patch("app.service_api_client.get_service_template", return_value=template_data)

    if template_type == "email":
        mocker.patch("app.service_api_client.get_reply_to_email_addresses", return_value=sender_data)
    else:
        mocker.patch("app.service_api_client.get_sms_senders", return_value=sender_data)

    client_request.post(
        ".set_sender",
        service_id=service_one["id"],
        template_id=fake_uuid,
        _data={"sender": "1234"},
    )

    with client_request.session_transaction() as session:
        assert session["sender_id"] == "1234"


@pytest.mark.parametrize(
    "template_type, sender_data",
    [
        (
            "email",
            [],
        ),
        ("sms", []),
    ],
)
def test_set_sender_redirects_if_no_sender_data(client_request, service_one, fake_uuid, template_type, sender_data, mocker):
    mocker.patch("app.service_api_client.get_service_template", return_value=create_template(template_type=template_type))

    if template_type == "email":
        mocker.patch("app.service_api_client.get_reply_to_email_addresses", return_value=[])
    if template_type == "sms":
        mocker.patch("app.service_api_client.get_sms_senders", return_value=[])

    client_request.get(
        ".set_sender",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _expected_status=302,
        _expected_url=url_for(
            ".send_one_off",
            service_id=service_one["id"],
            template_id=fake_uuid,
        ),
    )


def test_that_test_files_exist():
    assert len(test_spreadsheet_files) == 8
    assert len(test_non_spreadsheet_files) == 6


def test_should_not_allow_files_to_be_uploaded_without_the_correct_permission(
    client_request,
    mock_get_service_template,
    service_one,
    fake_uuid,
):
    template_id = fake_uuid
    service_one["permissions"] = []

    page = client_request.get(
        ".send_messages",
        service_id=SERVICE_ONE_ID,
        template_id=template_id,
        _follow_redirects=True,
    )

    assert page.select("main p")[0].text.strip() == "Sending text messages has been disabled for your service."
    assert page.select(".back-link")[0].text == "Back"
    assert page.select(".back-link")[0]["href"] == url_for(
        ".view_template",
        service_id=service_one["id"],
        template_id=template_id,
    )


def test_example_spreadsheet(
    client_request,
    mock_get_service_template_with_placeholders_same_as_recipient,
    fake_uuid,
):
    page = client_request.get(".send_messages", service_id=SERVICE_ONE_ID, template_id=fake_uuid)

    assert normalize_spaces(page.select_one("tbody tr").text) == ("1 phone number name date")


@pytest.mark.parametrize(
    "filename, acceptable_file, expected_status",
    list(zip(test_spreadsheet_files, repeat(True), repeat(302)))
    + list(zip(test_non_spreadsheet_files, repeat(False), repeat(200))),
)
def test_upload_files_in_different_formats(
    filename,
    acceptable_file,
    expected_status,
    client_request,
    service_one,
    mocker,
    mock_get_service_template,
    mock_s3_set_metadata,
    mock_s3_upload,
    fake_uuid,
):
    with open(filename, "rb") as uploaded:
        page = client_request.post(
            "main.send_messages",
            service_id=service_one["id"],
            template_id=fake_uuid,
            _data={"file": (BytesIO(uploaded.read()), filename)},
            _content_type="multipart/form-data",
            _expected_status=expected_status,
        )

    if acceptable_file:
        assert mock_s3_upload.call_args[0][1]["data"].strip() == (
            "phone number,name,favourite colour,fruit\r\n"
            "07739 468 050,Pete,Coral,tomato\r\n"
            "07527 125 974,Not Pete,Magenta,Avacado\r\n"
            "07512 058 823,Still Not Pete,Crimson,Pear"
        )
        # mock_s3_set_metadata.assert_called_once_with(SERVICE_ONE_ID, fake_uuid, original_file_name=filename)
    else:
        assert not mock_s3_upload.called
        assert normalize_spaces(page.select_one(".banner-dangerous").text) == (
            "Could not read {}. Try using a different file format.".format(filename)
        )


@pytest.mark.parametrize(
    "exception, expected_error_message",
    [
        (
            partial(UnicodeDecodeError, "codec", b"", 1, 2, "reason"),
            ("Could not read example.xlsx. Try using a different file format."),
        ),
        (
            BadZipFile,
            ("Could not read example.xlsx. Try using a different file format."),
        ),
        (
            XLRDError,
            ("Could not read example.xlsx. Try using a different file format."),
        ),
        (
            XLDateError,
            (
                "example.xlsx contains numbers or dates that GC Notify can’t understand. "
                "Try formatting all columns as ‘text’ or export your file as CSV."
            ),
        ),
        (
            XLDateNegative,
            (
                "example.xlsx contains numbers or dates that GC Notify can’t understand. "
                "Try formatting all columns as ‘text’ or export your file as CSV."
            ),
        ),
        (
            XLDateAmbiguous,
            (
                "example.xlsx contains numbers or dates that GC Notify can’t understand. "
                "Try formatting all columns as ‘text’ or export your file as CSV."
            ),
        ),
        (
            XLDateTooLarge,
            (
                "example.xlsx contains numbers or dates that GC Notify can’t understand. "
                "Try formatting all columns as ‘text’ or export your file as CSV."
            ),
        ),
    ],
)
def test_shows_error_if_parsing_exception(
    logged_in_client,
    mocker,
    mock_get_service_template,
    exception,
    expected_error_message,
):
    def _raise_exception_or_partial_exception(file_content, filename):
        raise exception()

    mocker.patch(
        "app.main.views.send.Spreadsheet.from_file",
        side_effect=_raise_exception_or_partial_exception,
    )

    response = logged_in_client.post(
        url_for("main.send_messages", service_id=SERVICE_ONE_ID, template_id=fake_uuid),
        data={"file": (BytesIO(b"example"), "example.xlsx")},
        content_type="multipart/form-data",
    )
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    assert normalize_spaces(page.select_one(".banner-dangerous").text) == (expected_error_message)


def test_upload_csv_file_with_errors_shows_check_page_with_errors(
    logged_in_client,
    service_one,
    mocker,
    mock_get_service_template_with_placeholders,
    mock_s3_upload,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    fake_uuid,
):
    mocker.patch(
        "app.main.views.send.s3download",
        return_value="""
            phone number,name
            +16502532222
            +16502532222
        """,
    )

    response = logged_in_client.post(
        url_for("main.send_messages", service_id=service_one["id"], template_id=fake_uuid),
        data={"file": (BytesIO("".encode("utf-8")), "invalid.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    with logged_in_client.session_transaction() as session:
        assert "file_uploads" not in session

    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert "Errors in current spreadsheet" in content
    assert "invalid.csv" in content
    assert "+16502532222" in content
    assert "Missing" in content
    assert "Choose file" in content


@pytest.mark.parametrize(
    "file_contents, expected_error, expected_heading",
    [
        (
            """
            telephone,name
            +16502532222
        """,
            ("Your spreadsheet is missing a column called ‘phone number’. " "Add the missing column."),
            "Check there’s a column for each variable",
        ),
        (
            """
            phone number
            +16502532222
        """,
            ("Your spreadsheet is missing a column called ‘name’. " "Add the missing column."),
            "Check there’s a column for each variable",
        ),
        (
            """
            phone number, phone number, PHONE_NUMBER
            +16502532223,++16502532224,+16502532225,
        """,
            (
                "Spreadsheets can only have one column called ‘phone number’ or ‘PHONE_NUMBER’ "
                "Delete or rename one of the columns for ‘phone number’ or ‘PHONE_NUMBER’."
            ),
            "Check there’s a column for each variable",
        ),
        (
            """
            phone number, name
        """,
            ("Spreadsheets need at least 1 row with recipient information. " "Add a row for each recipient."),
            "Check there’s a column for each variable",
        ),
        (
            "+16502532222",
            (
                "Your spreadsheet is missing columns and needs at least 1 row with recipient information. "
                "Add columns called ‘name’ and ‘phone number’ as well as 1 row for each recipient."
            ),
            "Check there’s a column for each variable",
        ),
        (
            "",
            (
                "Your spreadsheet is missing columns and needs at least 1 row with recipient information. "
                "Add columns called ‘name’ and ‘phone number’ as well as 1 row for each recipient."
            ),
            "Check there’s a column for each variable",
        ),
        (
            """
            phone number, name
            +16502532222, example
            , example
            +16502532222, example
        """,
            ("Enter missing data in 1 row"),
            "Edit your spreadsheet",
        ),
        (
            """
            phone number, name
            +16502532222, example
            +16502532222,
            +16502532222, example
        """,
            ("Enter missing data in 1 row"),
            "Edit your spreadsheet",
        ),
    ],
)
def test_upload_csv_file_with_missing_columns_shows_error(
    client_request,
    mocker,
    mock_get_service_template_with_placeholders,
    mock_s3_upload,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    service_one,
    fake_uuid,
    file_contents,
    expected_error,
    expected_heading,
):
    mocker.patch("app.main.views.send.s3download", return_value=file_contents)

    page = client_request.post(
        "main.send_messages",
        service_id=service_one["id"],
        template_id=fake_uuid,
        _data={"file": (BytesIO("".encode("utf-8")), "invalid.csv")},
        _follow_redirects=True,
    )

    with client_request.session_transaction() as session:
        assert "file_uploads" not in session

    assert normalize_spaces(page.find(role="alert").text) == expected_error
    assert normalize_spaces(page.select_one("h1").text) == expected_heading


@pytest.mark.parametrize(
    "file_contents, expected_error, expected_heading, num_cells_errors",
    [
        (
            f"""
                phone number, one, two, three
                +16502532222, {'a' * 155}, {'a' * 155}, {'a' * 155}
                +16502532222, {'a' * 613}, {'a' * 613}, {'a' * 613}
                +16502532222, {'a' * 50}, {'a' * 50}, {'a' * 50}
            """,
            "Maximum 612 characters. Some messages may be too long due to custom content.",
            "Added custom content exceeds the 612 character limit in 1 row",
            3,
        ),
        (
            f"""
                phone number, one, two, three
                +16502532222, {'a' * 613}, {'a' * 613}, {'a' * 613}
                +16502532222, {'a' * 619}, {'a' * 619}, {'a' * 619}
                +16502532222, {'a' * 700}, {'a' * 700}, {'a' * 700}
            """,
            "Maximum 612 characters. Some messages may be too long due to custom content.",
            "Added custom content exceeds the 612 character limit in 3 rows",
            9,
        ),
    ],
)
def test_upload_csv_variables_too_long_shows_banner_and_inline_cell_errors(
    client_request,
    mocker,
    mock_get_service_template_with_multiple_placeholders,
    mock_s3_upload,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    service_one,
    fake_uuid,
    file_contents,
    expected_error,
    expected_heading,
    num_cells_errors,
):
    mocker.patch("app.main.views.send.s3download", return_value=file_contents)
    page = client_request.post(
        "main.send_messages",
        service_id=service_one["id"],
        template_id=fake_uuid,
        _data={"file": (BytesIO("".encode("utf-8")), "invalid.csv")},
        _follow_redirects=True,
    )
    cell_errors = page.find_all("span", class_="table-field-error-label")

    with client_request.session_transaction() as session:
        assert "file_uploads" not in session

    assert normalize_spaces(page.find(role="alert").text) == expected_heading
    assert normalize_spaces(page.select_one("h1").text) == "Edit your spreadsheet"
    assert all(cell.text == expected_error for cell in cell_errors)
    assert len(cell_errors) == num_cells_errors


def test_upload_csv_invalid_extension(
    logged_in_client,
    mock_login,
    service_one,
    mock_get_service_template,
    fake_uuid,
):
    resp = logged_in_client.post(
        url_for("main.send_messages", service_id=service_one["id"], template_id=fake_uuid),
        data={"file": (BytesIO("contents".encode("utf-8")), "invalid.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "invalid.txt is not a spreadsheet that GC Notify can read" in resp.get_data(as_text=True)


def test_upload_valid_csv_redirects_to_check_page(
    client_request,
    mock_get_service_template_with_placeholders,
    mock_s3_upload,
    fake_uuid,
):
    client_request.post(
        "main.send_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _data={"file": (BytesIO("".encode("utf-8")), "valid.csv")},
        _expected_status=302,
        _expected_redirect=url_for(
            "main.check_messages",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
            upload_id=fake_uuid,
            original_file_name="valid.csv",
        ),
    )


@pytest.mark.parametrize(
    "extra_args, expected_recipient, expected_message",
    [
        (
            {},
            "To: 6502532223",
            "Test Service: A, Template <em>content</em> with & entity",
        ),
        (
            {"row_index": 2},
            "To: 6502532223",
            "Test Service: A, Template <em>content</em> with & entity",
        ),
        (
            {"row_index": 4},
            "To: 6502532225",
            "Test Service: C, Template <em>content</em> with & entity",
        ),
    ],
)
def test_upload_valid_csv_shows_preview_and_table(
    client_request,
    mocker,
    mock_get_live_service,
    mock_get_service_template_with_placeholders,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_set_metadata,
    fake_uuid,
    extra_args,
    expected_recipient,
    expected_message,
):
    with client_request.session_transaction() as session:
        session["file_uploads"] = {fake_uuid: {"template_id": fake_uuid}}

    mocker.patch(
        "app.main.views.send.s3download",
        return_value="""
        phone number,name,thing,thing,thing
        6502532223, A,   foo,  foo,  foo
        6502532224, B,   foo,  foo,  foo
        6502532225, C,   foo,  foo,
    """,
    )

    page = client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        original_file_name="example.csv",
        **extra_args,
    )

    mock_s3_set_metadata.assert_called_once_with(
        SERVICE_ONE_ID,
        fake_uuid,
        notification_count=3,
        template_id=fake_uuid,
        valid=True,
        original_file_name="example.csv",
    )

    assert page.h1.text.strip() == "Review before sending"
    assert page.select_one(".sms-message-recipient").text.strip() == expected_recipient
    assert page.select_one(".sms-message-wrapper").text.strip() == expected_message

    assert page.select_one(".table-field-index").text.strip() == "2"

    assert page.select_one(".table-field-index a")["href"] == url_for(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        row_index=2,
        original_file_name="example.csv",
        _anchor="ok-preview",
    )

    for row_index, row in enumerate(
        [
            (
                '<td class="table-field-left-aligned"> <div class="do-not-truncate-text">6502532223</div> </td>',  # noqa: E501
                '<td class="table-field-left-aligned"> <div class="do-not-truncate-text">A</div> </td>',  # noqa: E501
                (
                    '<td class="table-field-left-aligned"> '
                    '<div class="table-field-status-default"> '
                    "<ul> "
                    "<li>foo</li> <li>foo</li> <li>foo</li> "
                    "</ul> "
                    "</div> "
                    "</td>"
                ),
            ),
            (
                '<td class="table-field-left-aligned"> <div class="do-not-truncate-text">6502532224</div> </td>',  # noqa: E501
                '<td class="table-field-left-aligned"> <div class="do-not-truncate-text">B</div> </td>',  # noqa: E501
                (
                    '<td class="table-field-left-aligned"> '
                    '<div class="table-field-status-default"> '
                    "<ul> "
                    "<li>foo</li> <li>foo</li> <li>foo</li> "
                    "</ul> "
                    "</div> "
                    "</td>"
                ),
            ),
            (
                '<td class="table-field-left-aligned"> <div class="do-not-truncate-text">6502532225</div> </td>',  # noqa: E501
                '<td class="table-field-left-aligned"> <div class="do-not-truncate-text">C</div> </td>',  # noqa: E501
                (
                    '<td class="table-field-left-aligned"> '
                    '<div class="table-field-status-default"> '
                    "<ul> "
                    "<li>foo</li> <li>foo</li> "
                    "</ul> "
                    "</div> "
                    "</td>"
                ),
            ),
        ]
    ):
        for index, cell in enumerate(row):
            row = page.select("table tbody tr")[row_index]
            assert "id" not in row
            assert normalize_spaces(str(row.select("td")[index + 1])) == cell


def test_upload_valid_csv_only_sets_meta_if_filename_known(
    client_request,
    mocker,
    mock_get_live_service,
    mock_get_service_letter_template,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_set_metadata,
    fake_uuid,
):
    mocker.patch(
        "app.main.views.send.s3download",
        return_value="""
        addressline1, addressline2, postcode
        House       , 1 Street    , SW1A 1AA
    """,
    )
    mocker.patch(
        "app.main.views.send.get_page_count_for_letter",
        return_value=5,
    )
    mocker.patch("app.main.views.send.TemplatePreview.from_utils_template", return_value="foo")

    client_request.get(
        "main.check_messages_preview",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        filetype="pdf",
        _test_page_title=False,
    )

    assert len(mock_s3_set_metadata.call_args_list) == 0


def test_file_name_truncated_to_fit_in_s3_metadata(
    client_request,
    mocker,
    mock_get_live_service,
    mock_get_service_template_with_placeholders,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_set_metadata,
    fake_uuid,
):
    with client_request.session_transaction() as session:
        session["file_uploads"] = {fake_uuid: {"template_id": fake_uuid}}

    mocker.patch(
        "app.main.views.send.s3download",
        return_value="""
        phone number,name,thing,thing,thing
        6502532223, A,   foo,  foo,  foo
    """,
    )

    file_name = "ü😁" * 2000

    client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        original_file_name=file_name,
    )
    assert sys.getsizeof(file_name.encode("utf-8")) > 2000

    assert (
        sys.getsizeof(
            "".join(("{}{}".format(key, value) for key, value in mock_s3_set_metadata.call_args_list[0][1].items())).encode(
                "utf-8"
            )
        )
        == 1726
    )


def test_check_messages_replaces_invalid_characters_in_file_name(
    client_request,
    mocker,
    mock_get_live_service,
    mock_get_service_template_with_placeholders,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_set_metadata,
    fake_uuid,
):
    with client_request.session_transaction() as session:
        session["file_uploads"] = {fake_uuid: {"template_id": fake_uuid}}

    mocker.patch(
        "app.main.views.send.s3download",
        return_value="""
        phone number,name,thing,thing,thing
        6502532223, A,   foo,  foo,  foo
    """,
    )

    file_name = "ü😁’€"

    client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        original_file_name=file_name,
    )

    mock_s3_set_metadata.assert_called_once_with(
        SERVICE_ONE_ID,
        fake_uuid,
        notification_count=1,
        original_file_name="u?'?",
        template_id=fake_uuid,
        valid=True,
    )


def test_show_all_columns_if_there_are_duplicate_recipient_columns(
    client_request,
    mocker,
    mock_get_live_service,
    mock_get_service_template_with_placeholders,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    fake_uuid,
):
    with client_request.session_transaction() as session:
        session["file_uploads"] = {fake_uuid: {"template_id": fake_uuid}}

    mocker.patch(
        "app.main.views.send.s3download",
        return_value="""
        phone number, phone_number, PHONENUMBER
        6502532223,  6502532224,  6502532225
    """,
    )

    page = client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        _test_page_title=False,
    )

    assert normalize_spaces(page.select_one("thead").text) == ("Row in file1 phone number phone_number PHONENUMBER")
    assert normalize_spaces(page.select_one("tbody").text) == ("2 6502532225 6502532225 6502532225")


@pytest.mark.parametrize(
    "row_index, expected_status",
    [
        (0, 404),
        (1, 404),
        (2, 200),
        (3, 200),
        (4, 200),
        (5, 404),
    ],
)
def test_404_for_previewing_a_row_out_of_range(
    client_request,
    mocker,
    mock_get_live_service,
    mock_get_service_template_with_placeholders,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_set_metadata,
    fake_uuid,
    row_index,
    expected_status,
):
    with client_request.session_transaction() as session:
        session["file_uploads"] = {fake_uuid: {"template_id": fake_uuid}}

    mocker.patch(
        "app.main.views.send.s3download",
        return_value="""
        phone number,name,thing,thing,thing
        6502532223, A,   foo,  foo,  foo
        6502532224, B,   foo,  foo,  foo
        6502532225, C,   foo,  foo,  foo
    """,
    )

    client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        row_index=row_index,
        _expected_status=expected_status,
    )


@pytest.mark.parametrize(
    "user",
    (
        create_active_user_with_permissions(),
        create_active_caseworking_user(),
    ),
)
def test_send_test_doesnt_show_file_contents(
    client_request,
    mocker,
    mock_get_service_template,
    mock_s3_upload,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_has_no_jobs,
    service_one,
    fake_uuid,
    user,
):
    mocker.patch("app.user_api_client.get_user", return_value=user)
    mocker.patch(
        "app.main.views.send.s3download",
        return_value="""
        phone number
        6502532222
    """,
    )

    page = client_request.get(
        "main.send_test",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _follow_redirects=True,
    )

    assert page.select("h1")[0].text.strip() == "Review before sending"
    assert len(page.select("table")) == 0
    assert len(page.select(".banner-dangerous")) == 0
    assert page.select_one("button[type=submit]").text.strip() == "Send 1 text message"


@pytest.mark.parametrize(
    "user, endpoint, template_data, expected_recipient",
    [
        (
            create_active_user_with_permissions(),
            "main.send_test_step",
            create_sms_template(),
            "07700 900762",
        ),
        (
            create_active_user_with_permissions(),
            "main.send_test_step",
            create_email_template(),
            "test@user.canada.ca",
        ),
        (
            create_active_caseworking_user(),
            "main.send_test_step",
            create_email_template(),
            "caseworker@example.canada.ca",
        ),
        (
            create_active_user_with_permissions(),
            "main.send_test_step",
            create_letter_template(),
            None,
        ),
        (
            create_active_user_with_permissions(),
            "main.send_one_off_step",
            create_sms_template(),
            None,
        ),
        (
            create_active_user_with_permissions(),
            "main.send_one_off_step",
            create_email_template(),
            None,
        ),
        (
            create_active_user_with_permissions(),
            "main.send_one_off_step",
            create_letter_template(),
            None,
        ),
    ],
)
def test_send_test_step_redirects_if_session_not_setup(
    mocker,
    client_request,
    mock_get_service_statistics,
    mock_get_users_by_service,
    mock_has_no_jobs,
    fake_uuid,
    endpoint,
    template_data,
    expected_recipient,
    user,
):
    mocker.patch("app.user_api_client.get_user", return_value=user)

    mocker.patch("app.service_api_client.get_service_template", return_value=template_data)

    mocker.patch("app.main.views.send.get_page_count_for_letter", return_value=9)

    with client_request.session_transaction() as session:
        assert "recipient" not in session
        assert "placeholders" not in session

    client_request.login(user)
    client_request.get(
        endpoint,
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=0,
        _follow_redirects=True,
    )

    with client_request.session_transaction() as session:
        assert session["recipient"] == expected_recipient


def test_send_one_off_does_not_send_without_the_correct_permissions(
    client_request,
    mock_get_service_template,
    service_one,
    fake_uuid,
):
    template_id = fake_uuid
    service_one["permissions"] = []

    page = client_request.get(
        ".send_one_off",
        service_id=SERVICE_ONE_ID,
        template_id=template_id,
        _follow_redirects=True,
    )

    assert page.select("main p")[0].text.strip() == "Sending text messages has been disabled for your service."
    assert page.select(".back-link")[0].text == "Back"
    assert page.select(".back-link")[0]["href"] == url_for(
        ".view_template",
        service_id=service_one["id"],
        template_id=template_id,
    )


@pytest.mark.parametrize(
    "user",
    (
        create_active_user_with_permissions(),
        create_active_caseworking_user(),
    ),
)
@pytest.mark.parametrize(
    "template_data, partial_url, expected_h1, tour_shown",
    [
        (
            create_sms_template(),  # SMS
            partial(url_for, "main.send_test"),
            "What is the custom content in ((name)) ?",
            False,
        ),
        (
            create_sms_template(),
            partial(url_for, "main.send_one_off"),
            "Phone number",
            False,
        ),
        (
            create_sms_template(),
            partial(url_for, "main.send_test", help=1),
            "What is the custom content in ((name)) ?",
            True,
        ),
        (
            create_email_template(),
            partial(url_for, "main.send_test", help=1),
            "What is the custom content in ((thing)) ?",
            True,
        ),
        (
            create_email_template(),
            partial(url_for, "main.send_test"),
            "What is the custom content in ((thing)) ?",
            False,
        ),
        (
            create_email_template(),
            partial(url_for, "main.send_one_off"),
            "Email address",
            False,
        ),
    ],
)
def test_send_one_off_or_test_has_correct_page_titles(
    logged_in_client,
    service_one,
    mock_has_no_jobs,
    fake_uuid,
    mocker,
    template_data,
    partial_url,
    expected_h1,
    tour_shown,
    user,
):
    mocker.patch("app.user_api_client.get_user", return_value=user)
    mocker.patch("app.service_api_client.get_service_template", return_value=template_data)
    mocker.patch("app.main.views.send.get_page_count_for_letter", return_value=9)

    response = logged_in_client.get(
        partial_url(service_id=service_one["id"], template_id=fake_uuid, step_index=0),
        follow_redirects=True,
    )
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    assert response.status_code == 200
    assert page.h1.text.strip() == expected_h1


@pytest.mark.parametrize(
    "endpoint, step_index, prefilled, expected_field_label",
    [
        (
            "main.send_test_step",
            0,
            {"phone number": "6502532222"},
            "What is the custom content in ((one)) ?",
        ),
        (
            "main.send_test_step",
            1,
            {"phone number": "6502532222", "one": "one"},
            "What is the custom content in ((two)) ?",
        ),
        (
            "main.send_one_off_step",
            0,
            {},
            "Phone number",
        ),
        (
            "main.send_one_off_step",
            1,
            {"phone number": "6502532222"},
            "What is the custom content in ((one)) ?",
        ),
        (
            "main.send_one_off_step",
            2,
            {"phone number": "6502532222", "one": "one"},
            "What is the custom content in ((two)) ?",
        ),
    ],
)
def test_send_one_off_or_test_shows_placeholders_in_correct_order(
    client_request,
    fake_uuid,
    mock_has_no_jobs,
    mock_get_service_template_with_multiple_placeholders,
    endpoint,
    step_index,
    prefilled,
    expected_field_label,
):
    with client_request.session_transaction() as session:
        session["recipient"] = None
        session["placeholders"] = prefilled
        session["send_test_letter_page_count"] = None

    page = client_request.get(
        endpoint,
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=step_index,
    )

    assert normalize_spaces(page.select_one("label").text) == expected_field_label


@pytest.mark.parametrize(
    "template_type, expected_sticky",
    [
        ("sms", False),
        ("email", True),
        ("letter", True),
    ],
)
def test_send_one_off_has_sticky_header_for_email_and_letter(
    mocker,
    client_request,
    fake_uuid,
    mock_has_no_jobs,
    template_type,
    expected_sticky,
):
    mocker.patch(
        "app.service_api_client.get_service_template",
        return_value=create_template(template_type=template_type, postage="second" if template_type == "letter" else None),
    )
    mocker.patch("app.main.views.send.get_page_count_for_letter", return_value=9)

    page = client_request.get(
        "main.send_one_off_step",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=0,
        _follow_redirects=True,
    )

    assert bool(page.select(".stick-at-top-when-scrolling")) == expected_sticky


@pytest.mark.parametrize(
    "user",
    (
        create_active_user_with_permissions(),
        create_active_caseworking_user(),
    ),
)
def test_skip_link_will_not_show_on_sms_one_off_if_service_has_no_mobile_number(
    client_request,
    service_one,
    fake_uuid,
    mock_get_service_template,
    mock_has_no_jobs,
    mocker,
    user,
):
    user["mobile_number"] = None
    client_request.login(user)
    page = client_request.get(
        "main.send_one_off_step",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=0,
        _follow_redirects=True,
    )
    skip_links = page.select("a.mt-16.block.clear-both")
    assert not skip_links


@pytest.mark.parametrize("user", [create_active_user_with_permissions(), create_active_caseworking_user()])
def test_send_one_off_offers_link_to_upload(
    client_request,
    fake_uuid,
    mock_get_service_template,
    mock_has_jobs,
    user,
):
    client_request.login(user)

    page = client_request.get(
        "main.send_one_off",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _follow_redirects=True,
    )

    back_link = page.select("main a")[0]
    link = page.select("main a#list-uploader")[0]

    assert back_link.text.strip() == "Back"

    assert link.text.strip() == "Upload file with recipients"
    assert link["href"] == url_for(
        "main.send_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
    )


@pytest.mark.parametrize(
    "restricted, has_go_live_link",
    (
        (True, True),
        (False, False),
    ),
    ids=["trial service", "live service"],
)
def test_send_one_off_offers_link_to_request_to_go_live(
    client_request,
    fake_uuid,
    mock_get_service_template,
    mock_has_jobs,
    active_user_with_permissions,
    restricted,
    has_go_live_link,
    service_one,
):
    service = service_one
    service["restricted"] = restricted
    client_request.login(active_user_with_permissions, service=service)

    page = client_request.get(
        "main.add_recipients",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _follow_redirects=True,
    )

    links = page.select("main a")

    if has_go_live_link:
        assert "request to go live" in [link.text.strip() for link in links]
        assert url_for(
            "main.request_to_go_live",
            service_id=SERVICE_ONE_ID,
        ) in [link["href"] for link in links]
    else:
        assert "request to go live" not in [link.text.strip() for link in links]


@pytest.mark.parametrize(
    "user",
    (
        create_active_user_with_permissions(),
        create_active_caseworking_user(),
    ),
)
@pytest.mark.parametrize(
    "endpoint, step_index",
    (
        ("main.send_one_off_step", 1),
        ("main.send_test_step", 0),
    ),
)
def test_link_to_upload_not_offered_when_entering_personalisation(
    client_request,
    fake_uuid,
    mock_get_service_template_with_placeholders,
    mock_has_jobs,
    user,
    endpoint,
    step_index,
):
    client_request.login(user)

    with client_request.session_transaction() as session:
        session["recipient"] = "07900900900"
        session["placeholders"] = {"phone number": "07900900900"}

    page = client_request.get(
        endpoint,
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=step_index,
    )

    # We’re entering personalisation
    assert page.select_one("input[type=text]")["name"] == "placeholder_value"
    assert page.select_one("h1 label[for=placeholder_value]").text.strip() == "What is the custom content in ((name)) ?"
    # …but first link on the page is ‘Back’, so not preceeded by ‘Upload’
    assert page.select_one("main a").text == "Back"
    assert "Upload" not in page.select_one("main").text


@pytest.mark.parametrize(
    "user",
    (
        create_active_user_with_permissions(),
        create_active_caseworking_user(),
    ),
)
@pytest.mark.parametrize(
    "endpoint, expected_redirect, placeholders",
    [
        (
            "main.send_test_step",
            "main.send_test",
            {"name": "foo"},
        ),
        (
            "main.send_one_off_step",
            "main.send_one_off",
            {"name": "foo", "phone number": "6502532222"},
        ),
    ],
)
def test_send_test_redirects_to_end_if_step_out_of_bounds(
    client_request,
    mock_has_no_jobs,
    fake_uuid,
    endpoint,
    placeholders,
    expected_redirect,
    mocker,
    user,
):
    client_request.login(user)

    with client_request.session_transaction() as session:
        session["placeholders"] = placeholders

    client_request.get(
        endpoint,
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=999,
        _expected_status=302,
        _expected_redirect=url_for(
            expected_redirect,
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )


@pytest.mark.parametrize(
    "user",
    (
        create_active_user_with_permissions(),
        create_active_caseworking_user(),
    ),
)
@pytest.mark.parametrize(
    "endpoint, expected_redirect",
    [
        ("main.send_test_step", "main.send_test"),
        ("main.send_one_off_step", "main.send_one_off"),
    ],
)
def test_send_test_redirects_to_start_if_you_skip_steps(
    platform_admin_client,
    service_one,
    fake_uuid,
    mock_get_service_letter_template,
    mock_s3_upload,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_has_no_jobs,
    mocker,
    endpoint,
    expected_redirect,
    user,
):
    mocker.patch("app.user_api_client.get_user", return_value=user)

    with platform_admin_client.session_transaction() as session:
        session["send_test_letter_page_count"] = 1
        session["placeholders"] = {"address_line_1": "foo"}

    response = platform_admin_client.get(
        url_for(
            endpoint,
            service_id=service_one["id"],
            template_id=fake_uuid,
            step_index=7,  # letter template has 7 placeholders – we’re at the end
        )
    )
    assert response.status_code == 302
    assert response.location == url_for(
        expected_redirect,
        service_id=service_one["id"],
        template_id=fake_uuid,
    )


@pytest.mark.parametrize(
    "user",
    (
        create_active_user_with_permissions(),
        create_active_caseworking_user(),
    ),
)
@pytest.mark.parametrize(
    "endpoint, expected_redirect",
    [
        ("main.send_test_step", "main.send_test"),
        ("main.send_one_off_step", "main.send_one_off"),
    ],
)
def test_send_test_redirects_to_start_if_index_out_of_bounds_and_some_placeholders_empty(
    client_request,
    service_one,
    fake_uuid,
    mock_get_service_email_template,
    mock_s3_download,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_has_no_jobs,
    endpoint,
    expected_redirect,
    mocker,
    user,
):
    mocker.patch("app.user_api_client.get_user", return_value=user)
    with client_request.session_transaction() as session:
        session["placeholders"] = {"name": "foo"}

    client_request.get(
        endpoint,
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=999,
        _expected_status=302,
        _expected_redirect=url_for(
            expected_redirect,
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )


@pytest.mark.parametrize(
    "user",
    (
        create_active_user_with_permissions(),
        create_active_caseworking_user(),
    ),
)
@pytest.mark.parametrize(
    "endpoint, expected_redirect",
    [
        ("main.send_test", "main.send_test_step"),
        ("main.send_one_off", "main.send_one_off_step"),
    ],
)
def test_send_test_sms_message_redirects_with_help_argument(
    client_request,
    mocker,
    service_one,
    fake_uuid,
    endpoint,
    expected_redirect,
    user,
):
    mocker.patch("app.user_api_client.get_user", return_value=user)
    template = {"data": {"template_type": "sms", "folder": None}}
    mocker.patch("app.service_api_client.get_service_template", return_value=template)

    client_request.get(
        endpoint,
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        help=1,
        _expected_status=302,
        _expected_response=url_for(
            expected_redirect,
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
            step_index=0,
            help=1,
        ),
    )


@pytest.mark.parametrize(
    "user",
    (
        create_active_user_with_permissions(),
        create_active_caseworking_user(),
    ),
)
def test_send_test_email_message_without_placeholders_redirects_to_check_page(
    client_request,
    mocker,
    service_one,
    mock_s3_upload,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_has_no_jobs,
    fake_uuid,
    user,
):
    mocker.patch("app.user_api_client.get_user", return_value=user)
    template_data = create_template(template_id=fake_uuid, template_type="email")
    mocker.patch("app.service_api_client.get_service_template", return_value=template_data)

    with client_request.session_transaction() as session:
        session["recipient"] = "foo@bar.com"

    page = client_request.get(
        "main.send_test",
        step_index=0,
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _follow_redirects=True,
    )

    assert page.select("h1")[0].text.strip() == "Review before sending"


@pytest.mark.parametrize(
    "permissions, expected_back_link_endpoint, extra_args",
    (
        (
            {"send_messages", "manage_templates"},
            "main.view_template",
            {"template_id": unchanging_fake_uuid},
        ),
        (
            {"send_messages"},
            "main.view_template",
            {"template_id": unchanging_fake_uuid},
        ),
        (
            {"send_messages", "view_activity"},
            "main.view_template",
            {"template_id": unchanging_fake_uuid},
        ),
    ),
)
def test_send_test_sms_message_with_placeholders_shows_first_field(
    client_request,
    active_user_with_permissions,
    mock_login,
    mock_get_service,
    mock_get_service_template_with_placeholders,
    mock_has_no_jobs,
    permissions,
    expected_back_link_endpoint,
    extra_args,
):
    active_user_with_permissions["permissions"][SERVICE_ONE_ID] = permissions
    client_request.login(active_user_with_permissions)

    with client_request.session_transaction() as session:
        assert "placeholders" not in session

    page = client_request.get(
        "main.send_test",
        service_id=SERVICE_ONE_ID,
        template_id=unchanging_fake_uuid,
        _follow_redirects=True,
    )

    assert page.select("label")[0].text.strip() == "What is the custom content in ((name)) ?"
    assert page.select("input")[0]["name"] == "placeholder_value"
    assert page.select(".back-link")[0]["href"] == url_for(expected_back_link_endpoint, service_id=SERVICE_ONE_ID, **extra_args)
    with client_request.session_transaction() as session:
        assert session["recipient"] == "6502532222"


def test_send_test_sms_message_back_link_with_multiple_placeholders(
    client_request,
    mock_get_service_template_with_multiple_placeholders,
    mock_has_no_jobs,
):
    with client_request.session_transaction() as session:
        session["recipient"] = "6502532222"
        session["placeholders"] = {"phone number": "6502532222", "one": "bar"}
        session["send_test_letter_page_count"] = None

    page = client_request.get(
        "main.send_test_step",
        service_id=SERVICE_ONE_ID,
        template_id=unchanging_fake_uuid,
        step_index=2,
    )

    assert page.select_one(".back-link")["href"] == url_for(
        "main.send_test_step",
        service_id=SERVICE_ONE_ID,
        template_id=unchanging_fake_uuid,
        step_index=1,
    )


@pytest.mark.parametrize(
    "step_index, expected_back_link",
    (
        (
            0,
            partial(
                url_for,
                "main.start_tour",
            ),
        ),
        (
            1,
            partial(
                url_for,
                "main.send_test_step",
                step_index=0,
                help=2,
            ),
        ),
        (
            2,
            partial(
                url_for,
                "main.send_test_step",
                step_index=1,
                help=2,
            ),
        ),
    ),
)
def test_send_test_sms_message_back_link_in_tour(
    client_request,
    mock_get_service_template_with_multiple_placeholders,
    mock_has_no_jobs,
    step_index,
    expected_back_link,
):
    with client_request.session_transaction() as session:
        session["recipient"] = "6502532222"
        session["placeholders"] = {"phone number": "6502532222", "one": "bar"}
        session["send_test_letter_page_count"] = None

    page = client_request.get(
        "main.send_test_step",
        service_id=SERVICE_ONE_ID,
        template_id=unchanging_fake_uuid,
        step_index=step_index,
        help=2,
    )

    assert page.select_one(".back-link")["href"] == expected_back_link(
        service_id=SERVICE_ONE_ID,
        template_id=unchanging_fake_uuid,
    )


def test_send_test_letter_clears_previous_page_cache(
    platform_admin_client,
    mocker,
    service_one,
    mock_login,
    mock_get_service,
    mock_get_service_letter_template,
    fake_uuid,
):
    with platform_admin_client.session_transaction() as session:
        session["send_test_letter_page_count"] = "WRONG"

    response = platform_admin_client.get(
        url_for(
            "main.send_test",
            service_id=service_one["id"],
            template_id=fake_uuid,
        )
    )
    assert response.status_code == 302

    with platform_admin_client.session_transaction() as session:
        assert session["send_test_letter_page_count"] is None


def test_send_test_letter_redirects_to_right_url(
    platform_admin_client,
    fake_uuid,
    mock_get_service_letter_template,
    mock_s3_upload,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mocker,
):
    with platform_admin_client.session_transaction() as session:
        session["send_test_letter_page_count"] = 1
        session["recipient"] = ""
        session["placeholders"] = {
            "address line 1": "foo",
            "address line 2": "bar",
            "address line 3": "",
            "address line 4": "",
            "address line 5": "",
            "address line 6": "",
            "postcode": "SW1 1AA",
        }

    response = platform_admin_client.get(
        url_for(
            "main.send_one_off_step",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
            step_index=7,  # letter template has 7 placeholders – we’re at the end
        )
    )

    assert response.status_code == 302
    assert response.location.startswith(
        url_for(
            "main.check_notification",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        )
    )


def test_send_test_populates_field_from_session(
    client_request,
    mocker,
    service_one,
    mock_login,
    mock_get_service,
    mock_get_service_template_with_placeholders,
    fake_uuid,
):
    with client_request.session_transaction() as session:
        session["recipient"] = None
        session["placeholders"] = {}
        session["placeholders"]["name"] = "Jo"

    page = client_request.get(
        "main.send_test_step",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=0,
    )

    assert page.select("input")[0]["value"] == "Jo"


def test_send_test_caches_page_count(
    logged_in_client,
    mocker,
    service_one,
    mock_login,
    mock_get_service,
    mock_get_service_letter_template,
    fake_uuid,
):
    mocker.patch("app.main.views.send.get_page_count_for_letter", return_value=9)

    logged_in_client.get(
        url_for(
            "main.send_test",
            service_id=service_one["id"],
            template_id=fake_uuid,
        ),
        follow_redirects=True,
    )
    with logged_in_client.session_transaction() as session:
        assert session["send_test_letter_page_count"] == 9


def test_send_test_indicates_optional_address_columns(
    client_request,
    mocker,
    mock_get_service_letter_template,
    fake_uuid,
):
    mocker.patch("app.main.views.send.get_page_count_for_letter", return_value=1)

    with client_request.session_transaction() as session:
        session["recipient"] = None
        session["placeholders"] = {}

    page = client_request.get(
        "main.send_test_step",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=3,
    )

    assert normalize_spaces(page.select("h1 label")[0].text) == ("What is the custom content in ((address line 4)) ?")
    assert normalize_spaces(page.select("h1 + [id*='-hint']")[0].text) == ("Optional")
    assert page.select(".back-link")[0]["href"] == url_for(
        "main.send_one_off_step",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=2,
    )


def test_send_test_allows_empty_optional_address_columns(
    client_request,
    mocker,
    mock_get_service_letter_template,
    fake_uuid,
):
    mocker.patch("app.main.views.send.get_page_count_for_letter", return_value=1)

    with client_request.session_transaction() as session:
        session["recipient"] = None
        session["placeholders"] = {}

    client_request.post(
        "main.send_test_step",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        step_index=3,
        # no data here
        _expected_status=302,
        _expected_redirect=url_for(
            "main.send_test_step",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
            step_index=4,
        ),
    )


def test_send_test_sms_message_puts_submitted_data_in_session(
    client_request,
    service_one,
    mock_get_service_template_with_placeholders,
    mock_get_users_by_service,
    mock_get_service_statistics,
    fake_uuid,
):
    with client_request.session_transaction() as session:
        session["recipient"] = "6502532222"
        session["placeholders"] = {}

    client_request.post(
        "main.send_test_step",
        service_id=service_one["id"],
        template_id=fake_uuid,
        step_index=0,
        _data={"placeholder_value": "Jo"},
        _expected_status=302,
        _expected_redirect=url_for(
            "main.check_notification",
            service_id=service_one["id"],
            template_id=fake_uuid,
        ),
    )

    with client_request.session_transaction() as session:
        assert session["recipient"] == "6502532222"
        assert session["placeholders"]["name"] == "Jo"


@pytest.mark.parametrize("filetype", ["pdf", "png"])
def test_send_test_works_as_letter_preview(
    filetype,
    platform_admin_client,
    mock_get_service_letter_template,
    mock_get_users_by_service,
    mock_get_service_statistics,
    service_one,
    fake_uuid,
    mocker,
):
    service_one["permissions"] = ["letter"]
    mocker.patch("app.service_api_client.get_service", return_value={"data": service_one})
    mocker.patch("app.main.views.send.get_page_count_for_letter", return_value=1)
    mocked_preview = mocker.patch("app.main.views.send.TemplatePreview.from_utils_template", return_value="foo")

    service_id = service_one["id"]
    template_id = fake_uuid
    with platform_admin_client.session_transaction() as session:
        session["placeholders"] = {"address_line_1": "Jo Lastname"}
    response = platform_admin_client.get(
        url_for(
            "main.send_test_preview",
            service_id=service_id,
            template_id=template_id,
            filetype=filetype,
        )
    )

    mock_get_service_letter_template.assert_called_with(service_id, template_id, None)

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "foo"
    assert mocked_preview.call_args[0][0].id == template_id
    assert isinstance(mocked_preview.call_args[0][0], LetterImageTemplate)
    assert mocked_preview.call_args[0][0].values == {"address_line_1": "Jo Lastname"}
    assert mocked_preview.call_args[0][1] == filetype


def test_send_test_clears_session(
    client_request,
    mocker,
    service_one,
    fake_uuid,
):
    template = {"data": {"template_type": "sms", "folder": None}}
    mocker.patch("app.service_api_client.get_service_template", return_value=template)

    with client_request.session_transaction() as session:
        session["recipient"] = "6502532223"
        session["placeholders"] = {"foo": "bar"}

    client_request.get(
        "main.send_test",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _expected_status=302,
    )

    with client_request.session_transaction() as session:
        assert session["recipient"] is None
        assert session["placeholders"] == {}


def test_download_example_csv(
    logged_in_client,
    mocker,
    api_user_active,
    mock_login,
    mock_get_service,
    mock_get_service_template_with_placeholders_same_as_recipient,
    mock_has_permissions,
    fake_uuid,
):
    response = logged_in_client.get(
        url_for("main.get_example_csv", service_id=fake_uuid, template_id=fake_uuid),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert response.get_data(as_text=True) == ("phone number,name,date\r\n" "6502532222,example,example\r\n")
    assert "text/csv" in response.headers["Content-Type"]


def test_upload_csvfile_with_valid_phone_shows_all_numbers(
    logged_in_client,
    mock_get_service_template,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_live_service,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_set_metadata,
    service_one,
    fake_uuid,
    mock_s3_upload,
    mocker,
):
    mocker.patch(
        "app.main.views.send.s3download",
        return_value="\n".join(["phone number"] + ["65025322{0:02d}".format(final_two) for final_two in range(0, 53)]),
    )

    response = logged_in_client.post(
        url_for("main.send_messages", service_id=service_one["id"], template_id=fake_uuid),
        data={"file": (BytesIO("".encode("utf-8")), "valid.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    with logged_in_client.session_transaction() as session:
        assert "file_uploads" not in session

    mock_s3_set_metadata.assert_called_once_with(
        SERVICE_ONE_ID,
        fake_uuid,
        notification_count=53,
        template_id=fake_uuid,
        valid=True,
        original_file_name="valid.csv",
    )

    content = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "6502532201" in content
    assert "6502532209" in content
    assert "6502532210" not in content
    assert "Only shows the first 10 recipients" in content


@pytest.mark.parametrize(
    "international_sms_permission, should_allow_international",
    [
        (False, False),
        (True, True),
    ],
)
def test_upload_csvfile_with_international_validates(
    mocker,
    api_user_active,
    logged_in_client,
    mock_get_service_template,
    mock_s3_set_metadata,
    mock_s3_upload,
    mock_has_permissions,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    fake_uuid,
    international_sms_permission,
    should_allow_international,
    service_one,
):
    if international_sms_permission:
        service_one["permissions"] += ("sms", "international_sms")
    mocker.patch("app.service_api_client.get_service", return_value={"data": service_one})

    mocker.patch("app.main.views.send.s3download", return_value="")
    mock_recipients = mocker.patch(
        "app.main.views.send.RecipientCSV",
        return_value=RecipientCSV("", template_type="sms"),
    )

    response = logged_in_client.post(
        url_for("main.send_messages", service_id=fake_uuid, template_id=fake_uuid),
        data={"file": (BytesIO("".encode("utf-8")), "valid.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert mock_recipients.call_args[1]["international_sms"] == should_allow_international


def test_test_message_can_only_be_sent_now(
    client_request,
    mocker,
    service_one,
    mock_get_service_template,
    mock_s3_download,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_set_metadata,
    fake_uuid,
):
    content = client_request.get(
        "main.check_messages",
        service_id=service_one["id"],
        upload_id=fake_uuid,
        template_id=fake_uuid,
        from_test=True,
    )

    assert 'name="scheduled_for"' not in content


@pytest.mark.parametrize("when", ["", "2016-08-25T13:04:21.767198"])
def test_create_job_should_call_api(
    client_request,
    mock_create_job,
    mock_get_job,
    mock_get_notifications,
    mock_get_service_template,
    mock_get_service_data_retention,
    mocker,
    fake_uuid,
    when,
):
    data = mock_get_job(SERVICE_ONE_ID, fake_uuid)["data"]
    job_id = data["id"]
    original_file_name = data["original_file_name"]
    template_id = data["template"]
    notification_count = data["notification_count"]
    with client_request.session_transaction() as session:
        session["file_uploads"] = {
            fake_uuid: {
                "template_id": template_id,
                "notification_count": notification_count,
                "valid": True,
            }
        }

    page = client_request.post(
        "main.start_job",
        service_id=SERVICE_ONE_ID,
        upload_id=job_id,
        original_file_name=original_file_name,
        _data={"scheduled_for": when},
        _follow_redirects=True,
        _expected_status=200,
    )

    assert original_file_name in page.text

    mock_create_job.assert_called_with(
        job_id,
        SERVICE_ONE_ID,
        scheduled_for=when,
    )


def test_can_start_letters_job(platform_admin_client, mock_create_job, service_one, fake_uuid):
    with platform_admin_client.session_transaction() as session:
        session["file_uploads"] = {
            fake_uuid: {
                "template_id": fake_uuid,
                "notification_count": 123,
                "valid": True,
            }
        }

    response = platform_admin_client.post(
        url_for("main.start_job", service_id=service_one["id"], upload_id=fake_uuid),
        data={},
    )
    assert response.status_code == 302
    assert "just_sent=yes" in response.location


@pytest.mark.parametrize(
    "filetype, extra_args, expected_values, expected_page",
    [
        ("png", {}, {"postcode": "abc123", "addressline1": "123 street"}, 1),
        ("pdf", {}, {"postcode": "abc123", "addressline1": "123 street"}, None),
        (
            "png",
            {"row_index": 2},
            {"postcode": "abc123", "addressline1": "123 street"},
            1,
        ),
        (
            "png",
            {"row_index": 3},
            {"postcode": "cba321", "addressline1": "321 avenue"},
            1,
        ),
        (
            "png",
            {"row_index": 3, "page": 2},
            {"postcode": "cba321", "addressline1": "321 avenue"},
            "2",
        ),
        (
            # pdf expected page is always None
            "pdf",
            {"row_index": 3, "page": 2},
            {"postcode": "cba321", "addressline1": "321 avenue"},
            None,
        ),
    ],
)
def test_should_show_preview_letter_message(
    filetype,
    platform_admin_client,
    mock_get_service_letter_template,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    service_one,
    fake_uuid,
    mocker,
    extra_args,
    expected_values,
    expected_page,
):
    service_one["permissions"] = ["letter"]
    mocker.patch("app.service_api_client.get_service", return_value={"data": service_one})
    mocker.patch("app.main.views.send.get_page_count_for_letter", return_value=1)

    mocker.patch(
        "app.main.views.send.s3download",
        return_value="\n".join(["address line 1, postcode"] + ["123 street, abc123"] + ["321 avenue, cba321"]),
    )
    mocked_preview = mocker.patch("app.main.views.send.TemplatePreview.from_utils_template", return_value="foo")

    service_id = service_one["id"]
    template_id = fake_uuid
    with platform_admin_client.session_transaction() as session:
        session["file_uploads"] = {
            fake_uuid: {
                "template_id": fake_uuid,
                "notification_count": 1,
                "valid": True,
            }
        }

    response = platform_admin_client.get(
        url_for(
            "main.check_messages_preview",
            service_id=service_id,
            template_id=fake_uuid,
            upload_id=fake_uuid,
            filetype=filetype,
            **extra_args,
        )
    )

    mock_get_service_letter_template.assert_called_with(service_id, template_id, None)

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "foo"
    assert mocked_preview.call_args[0][0].id == template_id
    assert isinstance(mocked_preview.call_args[0][0], LetterPreviewTemplate)
    assert mocked_preview.call_args[0][1] == filetype
    assert mocked_preview.call_args[0][0].values == expected_values
    assert mocked_preview.call_args[1] == {"page": expected_page}


def test_dont_show_preview_letter_templates_for_bad_filetype(logged_in_client, mock_get_service_template, service_one, fake_uuid):
    resp = logged_in_client.get(
        url_for(
            "main.check_messages_preview",
            service_id=service_one["id"],
            template_id=fake_uuid,
            upload_id=fake_uuid,
            filetype="blah",
        )
    )
    assert resp.status_code == 404
    assert mock_get_service_template.called is False


@pytest.mark.parametrize(
    "route, response_code",
    [
        ("main.send_messages", 200),
        ("main.get_example_csv", 200),
        ("main.send_test", 302),
    ],
)
def test_route_permissions(
    mocker,
    app_,
    client,
    api_user_active,
    service_one,
    mock_get_service_template,
    mock_get_service_templates,
    mock_get_jobs,
    mock_get_notifications,
    mock_create_job,
    mock_s3_upload,
    fake_uuid,
    route,
    response_code,
):
    validate_route_permission(
        mocker,
        app_,
        "GET",
        response_code,
        url_for(route, service_id=service_one["id"], template_id=fake_uuid),
        ["view_activity", "send_messages"],
        api_user_active,
        service_one,
    )


@pytest.mark.parametrize(
    "route, response_code, method",
    [("main.check_notification", 200, "GET"), ("main.send_notification", 302, "POST")],
)
def test_route_permissions_send_check_notifications(
    mocker,
    app_,
    client,
    api_user_active,
    service_one,
    mock_send_notification,
    mock_get_service_template,
    mock_get_template_statistics,
    fake_uuid,
    route,
    response_code,
    method,
):
    with client.session_transaction() as session:
        session["recipient"] = "6502532223"
        session["placeholders"] = {"name": "a"}
    validate_route_permission_with_client(
        mocker,
        client,
        method,
        response_code,
        url_for(route, service_id=service_one["id"], template_id=fake_uuid),
        ["send_messages"],
        api_user_active,
        service_one,
    )


@pytest.mark.parametrize(
    "route, expected_status",
    [
        ("main.send_messages", 403),
        ("main.get_example_csv", 403),
        ("main.send_test", 403),
    ],
)
def test_route_permissions_sending(
    mocker,
    app_,
    client,
    api_user_active,
    service_one,
    mock_get_service_template,
    mock_get_service_templates,
    mock_get_jobs,
    mock_get_notifications,
    mock_create_job,
    fake_uuid,
    route,
    expected_status,
):
    validate_route_permission(
        mocker,
        app_,
        "GET",
        expected_status,
        url_for(
            route,
            service_id=service_one["id"],
            template_type="sms",
            template_id=fake_uuid,
        ),
        ["blah"],
        api_user_active,
        service_one,
    )


@pytest.mark.parametrize(
    "template_type, has_placeholders, extra_args, expected_url",
    [
        ("sms", False, dict(), partial(url_for, ".send_messages")),
        ("sms", True, dict(), partial(url_for, ".send_messages")),
        pytest.param("letter", False, dict(from_test=True), partial(url_for, ".send_test"), marks=pytest.mark.xfail),
        ("sms", True, dict(from_test=True), partial(url_for, ".send_test")),
    ],
)
def test_check_messages_back_link(
    client_request,
    mock_get_user_by_email,
    mock_get_users_by_service,
    mock_has_permissions,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_download,
    mock_s3_set_metadata,
    fake_uuid,
    mocker,
    template_type,
    has_placeholders,
    extra_args,
    expected_url,
):
    content = "Hi there ((name))" if has_placeholders else "Hi there"
    template_data = create_template(template_id=fake_uuid, template_type=template_type, content=content)
    mocker.patch("app.service_api_client.get_service_template", return_value=template_data)

    mocker.patch(
        "app.main.views.send.get_page_count_for_letter",
        return_value=5,
    )

    with client_request.session_transaction() as session:
        session["file_uploads"] = {
            fake_uuid: {
                "original_file_name": "valid.csv",
                "template_id": fake_uuid,
                "notification_count": 1,
                "valid": True,
            }
        }

    page = client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        upload_id=fake_uuid,
        template_id=fake_uuid,
        _test_page_title=False,
        **extra_args,
    )

    assert (page.findAll("a", {"class": "back-link"})[0]["href"]) == expected_url(
        service_id=SERVICE_ONE_ID, template_id=fake_uuid
    )


@pytest.mark.parametrize(
    "num_requested,expected_msg",
    [
        (0, "You cannot send all these text messages today"),
        (1, "You cannot send all these text messages today"),
    ],
    ids=["none_sent", "some_sent"],
)
def test_check_messages_shows_too_many_sms_messages_errors(
    app_,
    mocker,
    client_request,
    mock_get_service,  # set message_limit to 50 and sms limit to 20
    mock_get_users_by_service,
    mock_get_service_template,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_download,
    mock_s3_set_metadata,
    mock_get_limit_stats,
    fake_uuid,
    num_requested,
    expected_msg,
):
    # csv with 100 phone numbers
    mocker.patch(
        "app.main.views.send.s3download",
        return_value=",\n".join(["phone number"] + ([mock_get_users_by_service(None)[0]["mobile_number"]] * 30)),
    )
    mocker.patch(
        "app.service_api_client.get_service_statistics",
        return_value={
            "sms": {"requested": num_requested, "delivered": 0, "failed": 0},
            "email": {"requested": 0, "delivered": 0, "failed": 0},
        },
    )

    with client_request.session_transaction() as session:
        session["file_uploads"] = {
            fake_uuid: {
                "template_id": fake_uuid,
                "notification_count": 1,
                "valid": True,
            }
        }

    page = client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        original_file_name="valid.csv",
        _test_page_title=False,
    )

    # remove excess whitespace from element
    details = page.findAll("h2")[1]
    details = " ".join([line.strip() for line in details.text.split("\n") if line.strip() != ""])
    assert details == expected_msg


@pytest.fixture
def mock_notification_counts_client():
    with patch("app.main.views.send.notification_counts_client") as mock:
        yield mock


@pytest.fixture
def mock_daily_sms_fragment_count():
    with patch("app.main.views.send.daily_sms_fragment_count") as mock:
        yield mock


@pytest.fixture
def mock_daily_email_count():
    with patch("app.main.views.send.daily_email_count") as mock:
        yield mock


@pytest.fixture
def mock_get_service_template_annual_limits():
    with patch("app.service_api_client.get_service_template") as mock:
        yield mock


@pytest.mark.parametrize(
    "num_requested,expected_msg",
    [
        (0, "These messages exceed your daily limit"),
        (1, "These messages exceed your daily limit"),
    ],
    ids=["none_sent", "some_sent"],
)
def test_check_messages_shows_too_many_email_messages_errors(
    mocker,
    client_request,
    mock_get_service,  # set message_limit to 50
    mock_get_users_by_service,
    mock_get_service_email_template_without_placeholders,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_get_limit_stats,
    fake_uuid,
    num_requested,
    expected_msg,
):
    # csv with 100 phone numbers
    mocker.patch(
        "app.main.views.send.s3download",
        return_value=",\n".join(["email address"] + ([mock_get_users_by_service(None)[0]["email_address"]] * 100)),
    )
    mocker.patch(
        "app.service_api_client.get_service_statistics",
        return_value={
            "sms": {"requested": 0, "delivered": 0, "failed": 0},
            "email": {"requested": num_requested, "delivered": 0, "failed": 0},
        },
    )

    with client_request.session_transaction() as session:
        session["file_uploads"] = {
            fake_uuid: {
                "template_id": fake_uuid,
                "notification_count": 1,
                "valid": True,
            }
        }

    page = client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        original_file_name="valid.csv",
        _test_page_title=False,
    )

    assert page.find("h1").text.strip() == expected_msg

    # # remove excess whitespace from element
    # details = page.find(role="alert").findAll("p")[1]
    # details = " ".join([line.strip() for line in details.text.split("\n") if line.strip() != ""])
    # assert details == expected_msg


def test_check_messages_shows_trial_mode_error(
    client_request,
    mock_get_users_by_service,
    mock_get_service_template,
    mock_has_permissions,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    fake_uuid,
    mocker,
):
    mocker.patch(
        "app.main.views.send.s3download",
        return_value=("phone number,\n16502532229"),  # Not in team
    )

    with client_request.session_transaction() as session:
        session["file_uploads"] = {
            fake_uuid: {
                "template_id": "",
            }
        }

    page = client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        _test_page_title=False,
    )

    assert " ".join(page.find(role="alert").text.split()) == (
        "You cannot send to this phone number "
        "In trial mode, you can only send to yourself and team members. To send to more recipients, request to go live."
    )


@pytest.mark.parametrize(
    "uploaded_file_name",
    (
        pytest.param("applicants.ods"),  # normal job
        pytest.param("thisisatest.csv", marks=pytest.mark.xfail),  # different template version
        pytest.param("send_me_later.csv"),  # should look at scheduled job
        pytest.param("full_of_regret.csv", marks=pytest.mark.xfail),  # job is cancelled
    ),
)
def test_warns_if_file_sent_already(
    client_request,
    mock_get_users_by_service,
    mock_get_live_service,
    mock_get_service_template,
    mock_has_permissions,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    fake_uuid,
    mocker,
    uploaded_file_name,
):
    mocker.patch("app.main.views.send.s3download", return_value=("phone number,\n16502532222"))

    page = client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id="5d729fbd-239c-44ab-b498-75a985f3198f",
        upload_id=fake_uuid,
        original_file_name=uploaded_file_name,
        _test_page_title=False,
    )

    assert normalize_spaces(page.select_one(".banner-dangerous").text) == (
        "These messages have already been sent today " "If you need to re-send them, rename the file and upload it again."
    )

    mock_get_jobs.assert_called_once_with(SERVICE_ONE_ID, limit_days=0)


def test_check_messages_adds_sender_id_in_session_to_metadata(
    client_request,
    mocker,
    mock_get_live_service,
    mock_get_service_template,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_set_metadata,
    fake_uuid,
):
    mocker.patch("app.main.views.send.s3download", return_value=("phone number,\n+16502532222"))
    mocker.patch("app.main.views.send.get_sms_sender_from_session")

    with client_request.session_transaction() as session:
        session["file_uploads"] = {fake_uuid: {"template_id": fake_uuid}}
        session["sender_id"] = "fake-sender"

    client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        original_file_name="example.csv",
        _test_page_title=False,
    )

    mock_s3_set_metadata.assert_called_once_with(
        SERVICE_ONE_ID,
        fake_uuid,
        notification_count=1,
        template_id=fake_uuid,
        sender_id="fake-sender",
        valid=True,
        original_file_name="example.csv",
    )


def test_check_messages_shows_over_max_row_error(
    client_request,
    mock_get_users_by_service,
    mock_get_service_template_with_placeholders,
    mock_has_permissions,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    mock_s3_download,
    fake_uuid,
    mocker,
):
    mock_recipients = mocker.patch("app.main.views.send.RecipientCSV").return_value
    mock_recipients.max_rows = 11111
    mock_recipients.__len__.return_value = 99999
    mock_recipients.too_many_rows.return_value = True
    mock_recipients.sms_fragment_count = 20
    with client_request.session_transaction() as session:
        session["file_uploads"] = {
            fake_uuid: {
                "template_id": fake_uuid,
            }
        }

    page = client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        _test_page_title=False,
    )

    assert " ".join(page.find(role="alert").text.split()) == (
        "Include only 11,111 recipients per spreadsheet. "
        "To upload and send, return to the template and repeat the steps for each spreadsheet separately."
    )


@pytest.mark.parametrize("existing_session_items", [{}, {"recipient": "6502532223"}, {"name": "Jo"}])
def test_check_notification_redirects_if_session_not_populated(
    client_request,
    service_one,
    fake_uuid,
    existing_session_items,
    mock_get_service_template_with_placeholders,
    mock_get_template_statistics,
):
    with client_request.session_transaction() as session:
        session.update(existing_session_items)

    client_request.get(
        "main.check_notification",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _expected_status=301,
        _expected_redirect=url_for(
            "main.send_one_off_step",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
            step_index=1,
        ),
    )


@pytest.mark.parametrize("existing_session_items", [{}, {"recipient": "6502532223"}, {"name": "Jo"}])
def test_check_notification_redirects_with_help_if_session_not_populated(
    logged_in_client,
    service_one,
    fake_uuid,
    existing_session_items,
    mock_get_service_template_with_placeholders,
    mock_get_template_statistics,
):
    with logged_in_client.session_transaction() as session:
        session.update(existing_session_items)

    resp = logged_in_client.get(
        url_for(
            "main.check_notification",
            service_id=service_one["id"],
            template_id=fake_uuid,
            help="2",
        )
    )

    assert resp.location == url_for(
        "main.send_test",
        service_id=service_one["id"],
        template_id=fake_uuid,
        help="2",
    )


def test_check_notification_shows_preview(
    client_request, service_one, fake_uuid, mock_get_service_template, mock_get_template_statistics
):
    with client_request.session_transaction() as session:
        session["recipient"] = "6502532223"
        session["placeholders"] = {}

    page = client_request.get("main.check_notification", service_id=service_one["id"], template_id=fake_uuid)

    assert page.h1.text.strip() == "Review before sending"
    assert (page.findAll("a", {"class": "back-link"})[0]["href"]) == url_for(
        ".add_recipients", service_id=service_one["id"], template_id=fake_uuid
    )

    # assert tour not visible
    assert not page.select(".banner-tour")
    assert page.form.attrs["action"] == url_for(
        "main.send_notification",
        service_id=service_one["id"],
        template_id=fake_uuid,
        help="0",
    )


@pytest.mark.parametrize(
    "template, recipient, placeholders, expected_personalisation",
    (
        (
            mock_get_service_template,
            "6502532223",
            {"a": "b"},
            {"a": "b"},
        ),
        (
            mock_get_service_email_template,
            "test@example.com",
            {},
            {},
        ),
        (
            mock_get_service_letter_template,
            "foo",
            {},
            {},
        ),
    ),
)
def test_send_notification_submits_data(
    client_request,
    fake_uuid,
    mock_send_notification,
    mock_get_service_template,
    template,
    recipient,
    placeholders,
    expected_personalisation,
):
    with client_request.session_transaction() as session:
        session["recipient"] = recipient
        session["placeholders"] = placeholders

    client_request.post("main.send_notification", service_id=SERVICE_ONE_ID, template_id=fake_uuid)

    mock_send_notification.assert_called_once_with(
        SERVICE_ONE_ID,
        template_id=fake_uuid,
        recipient=recipient,
        personalisation=expected_personalisation,
        sender_id=None,
    )


def test_send_notification_clears_session(
    client_request,
    service_one,
    fake_uuid,
    mock_send_notification,
    mock_get_service_template,
):
    with client_request.session_transaction() as session:
        session["recipient"] = "6502532223"
        session["placeholders"] = {"a": "b"}
        session["send_step"] = "main.send_test_step"

    client_request.post("main.send_notification", service_id=service_one["id"], template_id=fake_uuid)

    with client_request.session_transaction() as session:
        assert "recipient" not in session
        assert "placeholders" not in session
        assert "send_step" not in session


def test_send_notification_redirects_if_missing_data(
    client_request,
    fake_uuid,
):
    with client_request.session_transaction() as session:
        session["placeholders"] = {"a": "b"}

    client_request.post(
        "main.send_notification",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _expected_status=302,
        _expected_redirect=url_for(
            ".send_one_off",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )


@pytest.mark.parametrize("extra_args, extra_redirect_args", [({}, {}), ({"help": "3"}, {"help": "3"})])
def test_send_notification_redirects_to_view_page(
    client_request,
    fake_uuid,
    mock_send_notification,
    mock_get_service_template,
    extra_args,
    extra_redirect_args,
):
    with client_request.session_transaction() as session:
        session["recipient"] = "6502532223"
        session["placeholders"] = {"a": "b"}

    client_request.post(
        "main.send_notification",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _expected_status=302,
        _expected_redirect=url_for(
            ".view_notification",
            service_id=SERVICE_ONE_ID,
            notification_id=fake_uuid,
            just_sent=True,
            **extra_redirect_args,
        ),
        **extra_args,
    )


TRIAL_MODE_MSG = "Can’t send to this recipient when service is in trial mode"
TOO_LONG_MSG = "Content for template has a character count greater than the limit of 612"
SERVICE_DAILY_LIMIT_MSG = "Exceeded send limits (1000) for today"


@pytest.mark.parametrize(
    "exception_msg, expected_h1, expected_err_details",
    [
        (
            TRIAL_MODE_MSG,
            "You cannot send to this phone number",
            "In trial mode, you can only send to yourself and team members. To send to more recipients, request to go live.",
        ),
        (
            TOO_LONG_MSG,
            "Message too long",
            "Text messages cannot be longer than 612 characters. Your message is 654 characters.",
        ),
        (
            SERVICE_DAILY_LIMIT_MSG,
            "These messages exceed your daily limit",
            "Your service is in trial mode. To send more messages, request to go live",
        ),
    ],
)
def test_send_notification_shows_error_if_400(
    client_request,
    service_one,
    fake_uuid,
    mocker,
    mock_get_service_template_with_placeholders,
    mock_get_template_statistics,
    exception_msg,
    expected_h1,
    expected_err_details,
):
    class MockHTTPError(HTTPError):
        message = exception_msg

    mocker.patch(
        "app.notification_api_client.send_notification",
        side_effect=MockHTTPError(),
    )
    with client_request.session_transaction() as session:
        session["recipient"] = "6502532223"
        session["placeholders"] = {"name": "a" * 600}

    page = client_request.post(
        "main.send_notification",
        service_id=service_one["id"],
        template_id=fake_uuid,
        _expected_status=200,
    )
    if exception_msg == SERVICE_DAILY_LIMIT_MSG:
        # assert normalize_spaces(page.select("h1")[0].text) == expected_h1
        assert normalize_spaces(page.select(".banner-dangerous p")[0].text) == expected_err_details
        assert not page.find("input[type=submit]")
    else:
        assert normalize_spaces(page.select(".banner-dangerous h1")[0].text) == expected_h1
        assert normalize_spaces(page.select(".banner-dangerous p")[0].text) == expected_err_details
        assert not page.find("input[type=submit]")


def test_send_notification_shows_email_error_in_trial_mode(
    client_request,
    fake_uuid,
    mocker,
    mock_get_service_email_template,
    mock_get_template_statistics,
):
    class MockHTTPError(HTTPError):
        message = TRIAL_MODE_MSG
        status_code = 400

    mocker.patch(
        "app.notification_api_client.send_notification",
        side_effect=MockHTTPError(),
    )
    with client_request.session_transaction() as session:
        session["recipient"] = "test@example.com"
        session["placeholders"] = {"date": "foo", "thing": "bar"}

    page = client_request.post(
        "main.send_notification",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        _expected_status=200,
    )

    assert normalize_spaces(page.select(".banner-dangerous h1")[0].text) == ("You cannot send to this email address")
    assert normalize_spaces(page.select(".banner-dangerous p")[0].text) == (
        "In trial mode, you can only send to yourself and team members. To send to more recipients, request to go live."
    )


@pytest.mark.parametrize(
    "endpoint, extra_args",
    [
        (
            "main.check_messages",
            {
                "template_id": uuid4(),
                "upload_id": uuid4(),
                "original_file_name": "example.csv",
            },
        ),
        ("main.send_one_off_step", {"template_id": uuid4(), "step_index": 0}),
    ],
)
@pytest.mark.parametrize(
    "reply_to_address",
    [
        None,
        uuid4(),
    ],
)
def test_reply_to_is_previewed_if_chosen(
    client_request,
    mocker,
    mock_get_service_email_template,
    mock_s3_download,
    mock_s3_set_metadata,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    get_default_reply_to_email_address,
    fake_uuid,
    endpoint,
    extra_args,
    reply_to_address,
):
    mocker.patch(
        "app.main.views.send.s3download",
        return_value="""
        email_address,date,thing
        notify@digital.cabinet-office.canada.ca,foo,bar
    """,
    )

    with client_request.session_transaction() as session:
        session["recipient"] = "notify@digital.cabinet-office.canada.ca"
        session["placeholders"] = {}
        session["file_uploads"] = {fake_uuid: {"template_id": fake_uuid}}
        session["sender_id"] = reply_to_address

    page = client_request.get(endpoint, service_id=SERVICE_ONE_ID, **extra_args)

    email_meta = page.select_one(".email-message-meta").text

    if reply_to_address:
        assert "test@example.com" in email_meta
    else:
        assert "test@example.com" not in email_meta


@pytest.mark.parametrize(
    "lang, expected_content",
    [
        (
            "fr",
            "De service one Répondre à test@example.com À ((adresse courriel)) Objet Template subject",
        ),
        (
            "en",
            "From service one Reply to test@example.com To ((email address)) Subject Template subject",
        ),
    ],
)
def test_preview_is_translated(client_request, mocker, get_default_reply_to_email_address, fake_uuid, lang, expected_content):
    mocker.patch("app.service_api_client.get_service_template", return_value=create_template(template_type="email"))
    mocker.patch("app.get_current_locale", return_value=lang)

    with client_request.session_transaction() as session:
        session["recipient"] = "notify@digital.cabinet-office.canada.ca"
        session["placeholders"] = {}
        session["sender_id"] = uuid4()

    page = client_request.get(
        "main.send_one_off_step",
        service_id=SERVICE_ONE_ID,
        template_id=uuid4(),
        step_index=0,
    )

    email_meta = normalize_spaces(page.select_one(".email-message-meta").text)
    assert expected_content == email_meta


@pytest.mark.parametrize(
    "endpoint, extra_args",
    [
        ("main.check_messages", {"template_id": uuid4(), "upload_id": uuid4()}),
        ("main.send_one_off_step", {"template_id": uuid4(), "step_index": 0}),
    ],
)
@pytest.mark.parametrize(
    "sms_sender",
    [
        None,
        uuid4(),
    ],
)
def test_sms_sender_is_previewed(
    client_request,
    mocker,
    mock_get_service_template,
    mock_s3_download,
    mock_s3_set_metadata,
    mock_get_users_by_service,
    mock_get_service_statistics,
    mock_get_template_statistics,
    mock_get_job_doesnt_exist,
    mock_get_jobs,
    get_default_sms_sender,
    fake_uuid,
    endpoint,
    extra_args,
    sms_sender,
):
    mocker.patch(
        "app.main.views.send.s3download",
        return_value="""
        phone number,date,thing
        +16502532222,foo,bar
    """,
    )

    with client_request.session_transaction() as session:
        session["recipient"] = "+16502532222"
        session["placeholders"] = {}
        session["file_uploads"] = {
            fake_uuid: {
                "template_id": fake_uuid,
                "notification_count": 1,
                "valid": True,
            }
        }
        session["sender_id"] = sms_sender
    page = client_request.get(endpoint, service_id=SERVICE_ONE_ID, **extra_args)

    sms_sender_on_page = page.select_one(".sms-message-sender")

    if sms_sender:
        assert sms_sender_on_page.text.strip() == "From: GOVUK"
    else:
        assert not sms_sender_on_page


def test_redirects_to_template_if_job_exists_already(
    client_request,
    mock_get_job,
    fake_uuid,
):
    client_request.get(
        "main.check_messages",
        service_id=SERVICE_ONE_ID,
        template_id=fake_uuid,
        upload_id=fake_uuid,
        original_file_name="example.csv",
        _expected_status=301,
        _expected_redirect=url_for(
            "main.send_messages",
            service_id=SERVICE_ONE_ID,
            template_id=fake_uuid,
        ),
    )


@pytest.mark.parametrize(
    "bulk_send_allowed, number_of_s3_upload_links",
    [
        (True, 1),
        (False, 0),
    ],
)
def test_s3_send_link_is_shown(
    logged_in_client,
    fake_uuid,
    mocker,
    bulk_send_allowed,
    number_of_s3_upload_links,
):
    mocker.patch("app.main.views.send.service_can_bulk_send", return_value=bulk_send_allowed)
    mocker.patch("app.service_api_client.get_service_template", return_value=create_template(template_type="email"))
    partial_url = partial(url_for, "main.send_one_off")
    response = logged_in_client.get(
        partial_url(service_id=SERVICE_ONE_ID, template_id=fake_uuid, step_index=0),
        follow_redirects=True,
    )
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    assert response.status_code == 200
    assert len(page.find_all(id="s3-send")) == number_of_s3_upload_links


@pytest.mark.parametrize(
    "bulk_send_allowed, expected_title",
    [
        (True, "Choose a list of email addresses from Amazon S3"),
        (False, "Emails are disabled"),
    ],
)
def test_s3_send_page_only_visible_to_hc(logged_in_client, fake_uuid, mocker, bulk_send_allowed, expected_title):
    class Object(object):
        pass

    expected_filenames = ["file0.csv", "file1.csv"]
    s3_file_objects = []
    for filename in expected_filenames:
        x = Object()
        x.key = filename
        s3_file_objects.append(x)

    mocker.patch("app.main.views.send.service_can_bulk_send", return_value=bulk_send_allowed)
    mocker.patch("app.main.views.send.list_bulk_send_uploads", return_value=s3_file_objects)
    mocker.patch("app.service_api_client.get_service_template", return_value=create_template(template_type="email"))
    partial_url = partial(url_for, "main.s3_send")
    response = logged_in_client.get(
        partial_url(service_id=SERVICE_ONE_ID, template_id=fake_uuid),
        follow_redirects=True,
    )
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    assert response.status_code == 200
    assert page.select("h1")[0].text.strip() == expected_title


def test_s3_send_shows_available_files(
    logged_in_client,
    fake_uuid,
    mocker,
):
    class Object(object):
        pass

    expected_filenames = ["file0.csv", "file1.csv"]
    s3_file_objects = []
    for filename in expected_filenames:
        x = Object()
        x.key = filename
        s3_file_objects.append(x)

    mocker.patch("app.main.views.send.service_can_bulk_send", return_value=True)
    mocker.patch("app.main.views.send.list_bulk_send_uploads", return_value=s3_file_objects)
    mocker.patch("app.service_api_client.get_service_template", return_value=create_template(template_type="email"))
    partial_url = partial(url_for, "main.s3_send")
    response = logged_in_client.get(
        partial_url(service_id=SERVICE_ONE_ID, template_id=fake_uuid),
        follow_redirects=True,
    )
    page = BeautifulSoup(response.data.decode("utf-8"), "html.parser")

    assert response.status_code == 200

    options = page.select(".multiple-choice label")
    multiple_choise_options = [x.text.strip() for x in options]

    assert multiple_choise_options == expected_filenames


class TestAnnualLimitsSend:
    @pytest.mark.parametrize(
        "num_being_sent, num_sent_today, num_sent_this_year, expect_to_see_annual_limit_msg, expect_to_see_daily_limit_msg",
        [
            # annual limit for mock_get_live_service is 10,000email/10,000sms
            # daily limit for mock_get_live_service is 1,000email/1,000sms
            # 1000 have already been sent today, trying to send 100 more [over both limits]
            (100, 1000, 10000, True, False),
            # No sent yet today or this year, trying to send 1001 [over both limits]
            (10001, 0, 0, True, False),
            # 600 have already been sent this year, trying to send 500 more [over annual limit but not daily]
            (500, 0, 9600, True, False),
            # No sent yet today or this year, trying to send 1001 [over daily limit but not annual]
            (1001, 0, 0, False, True),
            # No sent yet today or this year, trying to send 100 [over neither limit]
            (100, 0, 0, False, False),
        ],
        ids=[
            "email_over_both_limits",
            "email_over_both_limits2",
            "email_over_annual_but_not_daily",
            "email_over_daily_but_not_annual",
            "email_over_neither",
        ],
    )
    def test_email_send_fails_approrpiately_when_over_limits(
        self,
        mocker,
        client_request,
        mock_get_live_service,  # set email_annual_limit and sms_annual_limit to 1000
        mock_get_users_by_service,
        mock_get_service_email_template_without_placeholders,
        mock_get_template_statistics,
        mock_get_job_doesnt_exist,
        mock_get_jobs,
        mock_s3_set_metadata,
        mock_notification_counts_client,
        mock_daily_sms_fragment_count,
        mock_daily_email_count,
        fake_uuid,
        num_being_sent,
        num_sent_today,
        num_sent_this_year,
        expect_to_see_annual_limit_msg,
        expect_to_see_daily_limit_msg,
        app_,
    ):
        with set_config(app_, "FF_ANNUAL_LIMIT", True):
            mocker.patch(
                "app.main.views.send.s3download",
                return_value=",\n".join(
                    ["email address"] + ([mock_get_users_by_service(None)[0]["email_address"]] * num_being_sent)
                ),
            )

            mock_notification_counts_client.get_limit_stats.return_value = {
                "email": {
                    "annual": {
                        "limit": 1,  # doesn't matter for our test
                        "sent": 1,  # doesn't matter for our test
                        "remaining": 10000
                        - num_sent_this_year
                        - num_sent_today,  # The number of email notifications remaining this year
                    },
                    "daily": {
                        "limit": 1,  # doesn't matter for our test
                        "sent": 1,  # doesn't matter for our test
                        "remaining": 1000 - num_sent_today,  # The number of email notifications remaining today
                    },
                }
            }

            # mock that we've already sent `emails_sent_today` emails today
            mock_daily_email_count.return_value = num_sent_today
            mock_daily_sms_fragment_count.return_value = 900  # not used in test but needs a value

            with client_request.session_transaction() as session:
                session["file_uploads"] = {
                    fake_uuid: {
                        "template_id": fake_uuid,
                        "notification_count": 1,
                        "valid": True,
                    }
                }

            page = client_request.get(
                "main.check_messages",
                service_id=SERVICE_ONE_ID,
                template_id=fake_uuid,
                upload_id=fake_uuid,
                original_file_name="valid.csv",
                _test_page_title=False,
            )

            if expect_to_see_annual_limit_msg:
                assert page.find(attrs={"data-testid": "exceeds-annual"}) is not None
            else:
                assert page.find(attrs={"data-testid": "exceeds-annual"}) is None

            if expect_to_see_daily_limit_msg:
                assert page.find(attrs={"data-testid": "exceeds-daily"}) is not None
            else:
                assert page.find(attrs={"data-testid": "exceeds-daily"}) is None

    @pytest.mark.parametrize(
        "num_being_sent, num_sent_today, num_sent_this_year, expect_to_see_annual_limit_msg, expect_to_see_daily_limit_msg",
        [
            # annual limit for mock_get_live_service is 10,000email/10,000sms
            # daily limit for mock_get_live_service is 1,000email/1,000sms
            # 1000 have already been sent today, trying to send 100 more [over both limits]
            (100, 1000, 10000, True, False),
            # No sent yet today or this year, trying to send 1001 [over both limits]
            (10001, 0, 0, True, False),
            # 600 have already been sent this year, trying to send 500 more [over annual limit but not daily]
            (500, 0, 9600, True, False),
            # No sent yet today or this year, trying to send 1001 [over daily limit but not annual]
            (1001, 0, 0, False, True),
            # No sent yet today or this year, trying to send 100 [over neither limit]
            (100, 0, 0, False, False),
        ],
        ids=[
            "sms_over_both_limits",
            "sms_over_both_limits2",
            "sms_over_annual_but_not_daily",
            "sms_over_daily_but_not_annual",
            "sms_over_neither",
        ],
    )
    def test_sms_send_fails_approrpiately_when_over_limits(
        self,
        mocker,
        client_request,
        mock_get_live_service,  # set email_annual_limit and sms_annual_limit to 1000
        mock_get_users_by_service,
        mock_get_service_sms_template_without_placeholders,
        mock_get_template_statistics,
        mock_get_job_doesnt_exist,
        mock_get_jobs,
        mock_s3_set_metadata,
        mock_notification_counts_client,
        mock_daily_sms_fragment_count,
        mock_daily_email_count,
        fake_uuid,
        num_being_sent,
        num_sent_today,
        num_sent_this_year,
        expect_to_see_annual_limit_msg,
        expect_to_see_daily_limit_msg,
        app_,
    ):
        with set_config(app_, "FF_ANNUAL_LIMIT", True):  # REMOVE LINE WHEN FF REMOVED
            mocker.patch(
                "app.main.views.send.s3download",
                return_value=",\n".join(
                    ["phone number"] + ([mock_get_users_by_service(None)[0]["mobile_number"]] * num_being_sent)
                ),
            )
            mock_notification_counts_client.get_limit_stats.return_value = {
                "sms": {
                    "annual": {
                        "limit": 1,  # doesn't matter for our test
                        "sent": 1,  # doesn't matter for our test
                        "remaining": 10000
                        - num_sent_this_year
                        - num_sent_today,  # The number of email notifications remaining this year
                    },
                    "daily": {
                        "limit": 1,  # doesn't matter for our test
                        "sent": 1,  # doesn't matter for our test
                        "remaining": 1000 - num_sent_today,  # The number of email notifications remaining today
                    },
                }
            }
            # mock that we've already sent `num_sent_today` emails today
            mock_daily_email_count.return_value = 900  # not used in test but needs a value
            mock_daily_sms_fragment_count.return_value = num_sent_today

            with client_request.session_transaction() as session:
                session["file_uploads"] = {
                    fake_uuid: {
                        "template_id": fake_uuid,
                        "notification_count": 1,
                        "valid": True,
                    }
                }

            page = client_request.get(
                "main.check_messages",
                service_id=SERVICE_ONE_ID,
                template_id=fake_uuid,
                upload_id=fake_uuid,
                original_file_name="valid.csv",
                _test_page_title=False,
            )

            if expect_to_see_annual_limit_msg:
                assert page.find(attrs={"data-testid": "exceeds-annual"}) is not None
            else:
                assert page.find(attrs={"data-testid": "exceeds-annual"}) is None

            if expect_to_see_daily_limit_msg:
                assert page.find(attrs={"data-testid": "exceeds-daily"}) is not None
            else:
                assert page.find(attrs={"data-testid": "exceeds-daily"}) is None

    @pytest.mark.parametrize(
        "num_to_send, remaining_daily, remaining_annual, error_shown",
        [
            (2, 2, 2, "none"),
            (5, 5, 4, "annual"),
            (5, 4, 5, "daily"),
            (5, 4, 4, "annual"),
        ],
    )
    def test_correct_error_displayed(
        self,
        mocker,
        client_request,
        mock_get_live_service,  # set email_annual_limit and sms_annual_limit to 1000
        mock_get_users_by_service,
        mock_get_service_email_template_without_placeholders,
        mock_get_template_statistics,
        mock_get_job_doesnt_exist,
        mock_get_jobs,
        mock_s3_set_metadata,
        mock_daily_email_count,
        mock_notification_counts_client,
        fake_uuid,
        num_to_send,
        remaining_daily,
        remaining_annual,
        error_shown,
        app_,
    ):
        with set_config(app_, "FF_ANNUAL_LIMIT", True):  # REMOVE LINE WHEN FF REMOVED
            # mock that `num_sent_this_year` have already been sent this year
            mock_notification_counts_client.get_limit_stats.return_value = {
                "email": {
                    "annual": {
                        "limit": 1,  # doesn't matter for our test
                        "sent": 1,  # doesn't matter for our test
                        "remaining": remaining_annual,  # The number of email notifications remaining this year
                    },
                    "daily": {
                        "limit": 1,  # doesn't matter for our test
                        "sent": 1,  # doesn't matter for our test
                        "remaining": remaining_daily,  # The number of email notifications remaining today
                    },
                }
            }

            # only change this value when we're expecting an error
            if error_shown != "none":
                mock_daily_email_count.return_value = 1000 - (
                    num_to_send - 1
                )  # svc limit is 1000 - exceeding the daily limit is calculated based off of this
            else:
                mock_daily_email_count.return_value = 0  # none sent

            mocker.patch(
                "app.main.views.send.s3download",
                return_value=",\n".join(
                    ["email address"] + ([mock_get_users_by_service(None)[0]["email_address"]] * num_to_send)
                ),
            )
            with client_request.session_transaction() as session:
                session["file_uploads"] = {
                    fake_uuid: {
                        "template_id": fake_uuid,
                        "notification_count": 1,
                        "valid": True,
                    }
                }
            page = client_request.get(
                "main.check_messages",
                service_id=SERVICE_ONE_ID,
                template_id=fake_uuid,
                upload_id=fake_uuid,
                original_file_name="valid.csv",
                _test_page_title=False,
            )

            if error_shown == "annual":
                assert page.find(attrs={"data-testid": "exceeds-annual"}) is not None
                assert page.find(attrs={"data-testid": "exceeds-daily"}) is None
            elif error_shown == "daily":
                assert page.find(attrs={"data-testid": "exceeds-annual"}) is None
                assert page.find(attrs={"data-testid": "exceeds-daily"}) is not None
            elif error_shown == "none":
                assert page.find(attrs={"data-testid": "exceeds-annual"}) is None
                assert page.find(attrs={"data-testid": "exceeds-daily"}) is None

    @pytest.mark.parametrize(
        "notification_type, exception_msg_api, expected_error_msg_admin",
        [
            ("email", "Exceeded annual email sending", "These messages exceed the annual limit"),
            ("sms", "Exceeded annual SMS sending", "These messages exceed the annual limit"),
        ],
    )
    def test_error_msgs_from_api_for_one_off(
        self,
        client_request,
        service_one,
        fake_uuid,
        mocker,
        mock_get_service_template_with_placeholders,
        mock_get_template_statistics,
        notification_type,
        exception_msg_api,
        expected_error_msg_admin,
    ):
        class MockHTTPError(HTTPError):
            message = exception_msg_api

        mocker.patch(
            "app.notification_api_client.send_notification",
            side_effect=MockHTTPError(),
        )

        if notification_type == "sms":
            with client_request.session_transaction() as session:
                session["recipient"] = "6502532223"
                session["placeholders"] = {"name": "a" * 600}
        elif notification_type == "email":
            with client_request.session_transaction() as session:
                session["recipient"] = "test@example.com"
                session["placeholders"] = {"name": "a" * 600}

        page = client_request.post(
            "main.send_notification",
            service_id=service_one["id"],
            template_id=fake_uuid,
            _expected_status=200,
        )

        assert normalize_spaces(page.select("h1")[0].text) == expected_error_msg_admin

    @pytest.mark.parametrize(
        "exception_msg_api, expected_error_msg_admin",
        [
            # ("email","Exceeded annual email sending", "These messages exceed the annual limit"),
            ("Exceeded annual SMS sending", "These messages exceed the annual limit")
        ],
    )
    def test_error_msgs_from_api_for_bulk(
        self,
        client_request,
        mock_create_job,
        mock_get_job,
        mock_get_notifications,
        mock_get_service_template,
        mock_get_service_data_retention,
        mocker,
        fake_uuid,
        exception_msg_api,
        expected_error_msg_admin,
    ):
        class MockHTTPError(HTTPError):
            message = exception_msg_api

        data = mock_get_job(SERVICE_ONE_ID, fake_uuid)["data"]
        job_id = data["id"]
        original_file_name = data["original_file_name"]
        template_id = data["template"]
        notification_count = data["notification_count"]
        with client_request.session_transaction() as session:
            session["file_uploads"] = {
                fake_uuid: {
                    "template_id": template_id,
                    "notification_count": notification_count,
                    "valid": True,
                }
            }

        mocker.patch(
            "app.job_api_client.create_job",
            side_effect=MockHTTPError(),
        )
        page = client_request.post(
            "main.start_job",
            service_id=SERVICE_ONE_ID,
            upload_id=job_id,
            original_file_name=original_file_name,
            _data={},
            _follow_redirects=True,
            _expected_status=200,
        )

        assert normalize_spaces(page.select("h1")[0].text) == expected_error_msg_admin
