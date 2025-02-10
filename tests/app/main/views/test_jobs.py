import json
import uuid

import pytest
from flask import url_for
from freezegun import freeze_time

from app.main.views.jobs import get_available_until_date
from tests import job_json, notification_json, sample_uuid
from tests.conftest import (
    JOB_API_KEY_NAME,
    SERVICE_ONE_ID,
    create_active_caseworking_user,
    create_active_user_with_permissions,
    create_template,
    mock_get_notifications,
    normalize_spaces,
)


@pytest.mark.parametrize(
    "user",
    [
        create_active_user_with_permissions(),
        create_active_caseworking_user(),
    ],
)
@pytest.mark.parametrize(
    "expected_rows",
    [
        (
            ("List name Details"),
            ("send_me_later.csv " "Starting 2016-01-01 11:09:00.061258 Scheduled to send to 30 recipients"),
            ("even_later.csv " "Starting 2016-01-01 23:09:00.061258 Scheduled to send to 30 recipients"),
            ("List name Sending Delivered Failed"),
            ("export 1/1/2016.xls " "Sent 2012-12-12T12:12:00.000000+0000 30 0 0"),
            ("all email addresses.xlsx " "Sent 2012-12-12T12:12:00.000000+0000 30 0 0"),
            ("applicants.ods " "Sent 2012-12-12T12:12:00.000000+0000 30 0 0"),
            ("thisisatest.csv " "Sent 2012-12-12T12:12:00.000000+0000 30 0 0"),
        )
    ],
)
@freeze_time("2012-12-12 12:12")
# This test assumes EST
def test_jobs_page_shows_scheduled_jobs(
    client_request,
    service_one,
    active_user_with_permissions,
    mock_get_jobs,
    fake_uuid,
    user,
    expected_rows,
):
    client_request.login(user)
    page = client_request.get("main.view_jobs", service_id=service_one["id"])

    for index, row in enumerate(expected_rows):
        assert normalize_spaces(page.select("tr")[index].text) == row


def test_jobs_page_shows_empty_message_when_no_jobs_scheduled(
    client_request, service_one, active_user_with_permissions, mock_get_no_jobs, fake_uuid
):
    client_request.login(create_active_user_with_permissions())
    page = client_request.get("main.view_jobs", service_id=service_one["id"])

    assert "You have no scheduled messages at the moment" in str(page.contents)
    assert "Scheduled messages will be sent soon" in str(page.contents)


@pytest.mark.parametrize(
    "user",
    [
        create_active_user_with_permissions,
        create_active_caseworking_user,
    ],
)
def test_get_jobs_shows_page_links(
    client_request,
    active_user_with_permissions,
    mock_get_jobs,
    user,
    fake_uuid,
):
    client_request.login(user(fake_uuid))
    page = client_request.get("main.view_jobs", service_id=SERVICE_ONE_ID)

    assert "Next page" in page.find("div", {"class": "next-page"}).text
    assert "Previous page" in page.find("div", {"class": "previous-page"}).text


@pytest.mark.parametrize(
    "user",
    [
        create_active_user_with_permissions,
        create_active_caseworking_user,
    ],
)
@freeze_time("2012-12-12 12:12")
def test_jobs_page_doesnt_show_scheduled_on_page_2(
    client_request,
    service_one,
    active_user_with_permissions,
    mock_get_jobs,
    fake_uuid,
    user,
):
    client_request.login(user(fake_uuid))
    page = client_request.get("main.view_jobs", service_id=service_one["id"], page=2)

    for index, row in enumerate(
        (
            ("List name Sending Delivered Failed"),
            ("export 1/1/2016.xls " "Sent 2012-12-12T12:12:00.000000+0000 30 0 0"),
            ("all email addresses.xlsx " "Sent 2012-12-12T12:12:00.000000+0000 30 0 0"),
            ("applicants.ods " "Sent 2012-12-12T12:12:00.000000+0000 30 0 0"),
            ("thisisatest.csv " "Sent 2012-12-12T12:12:00.000000+0000 30 0 0"),
        )
    ):
        assert normalize_spaces(page.select("tr")[index].text) == row


@pytest.mark.parametrize(
    "user",
    [
        create_active_user_with_permissions,
        create_active_caseworking_user,
    ],
)
@pytest.mark.parametrize(
    "status_argument, expected_api_call",
    [
        (
            "",
            [
                "created",
                "pending",
                "sending",
                "pending-virus-check",
                "delivered",
                "sent",
                "returned-letter",
                "failed",
                "temporary-failure",
                "permanent-failure",
                "technical-failure",
                "virus-scan-failed",
                "validation-failed",
            ],
        ),
        ("sending", ["sending", "created", "pending", "pending-virus-check"]),
        ("delivered", ["delivered", "sent", "returned-letter"]),
        (
            "failed",
            [
                "failed",
                "temporary-failure",
                "permanent-failure",
                "technical-failure",
                "virus-scan-failed",
                "validation-failed",
            ],
        ),
    ],
)
@freeze_time("2016-01-01 11:09:00.061258")
def test_should_show_page_for_one_job(
    client_request,
    active_user_with_permissions,
    mock_get_service_template,
    mock_get_job,
    mocker,
    mock_get_notifications,
    mock_get_service_data_retention,
    fake_uuid,
    status_argument,
    expected_api_call,
    user,
    app_,
):
    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
        status=status_argument,
    )

    assert page.h1.text.strip() == "Delivery report"
    dashboard_table = page.find_all("table")[1]
    assert " ".join(dashboard_table.find("tbody").find("tr").text.split()) == (
        "6502532222 template content No Delivered 11:10:00.061258"
    )
    assert page.find("div", {"data-key": "notifications"})["data-resource"] == url_for(
        "main.view_job_updates",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
        status=status_argument,
        pe_filter="",
    )
    csv_link = page.select_one("a[download]")
    assert csv_link["href"] == url_for(
        "main.view_job_csv",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
        status=status_argument,
    )
    assert csv_link.text == "Download this report"
    assert page.find("time", {"id": "time-left"}).text.split(" ")[0] == "2016-01-09"

    assert normalize_spaces(dashboard_table.select_one("tbody tr").text) == normalize_spaces(
        "6502532222 " "template content " "No " "Delivered 11:10:00.061258"
    )
    assert dashboard_table.select_one("tbody tr a")["href"] == url_for(
        "main.view_notification",
        service_id=SERVICE_ONE_ID,
        notification_id=sample_uuid(),
        from_job=fake_uuid,
    )

    mock_get_notifications.assert_called_with(SERVICE_ONE_ID, fake_uuid, status=expected_api_call)


@freeze_time("2016-01-01 11:09:00.061258")
def test_should_show_page_for_one_job_with_flexible_data_retention(
    client_request,
    active_user_with_permissions,
    mock_get_service_template,
    mock_get_job,
    mocker,
    mock_get_notifications,
    mock_get_service_data_retention,
    fake_uuid,
):
    mock_get_service_data_retention.side_effect = [[{"days_of_retention": 10, "notification_type": "sms"}]]
    page = client_request.get("main.view_job", service_id=SERVICE_ONE_ID, job_id=fake_uuid, status="delivered")

    assert page.find("time", {"id": "time-left"}).text.split(" ")[0] == "2016-01-12"
    assert "Cancel sending these letters" not in page


def test_get_jobs_should_tell_user_if_more_than_one_page(
    client_request,
    fake_uuid,
    service_one,
    mock_get_job,
    mock_get_service_template,
    mock_get_notifications_with_previous_next,
    mock_get_service_data_retention,
):
    page = client_request.get(
        "main.view_job",
        service_id=service_one["id"],
        job_id=fake_uuid,
        status="",
    )
    assert page.find("p", {"class": "table-show-more-link"}).text.strip() == "Only showing the first 50 rows"


def test_should_show_job_in_progress(
    client_request,
    service_one,
    active_user_with_permissions,
    mock_get_service_template,
    mock_get_job_in_progress,
    mocker,
    mock_get_notifications,
    mock_get_service_data_retention,
    fake_uuid,
):
    page = client_request.get(
        "main.view_job",
        service_id=service_one["id"],
        job_id=fake_uuid,
    )
    assert page.find("div", {"class": "dashboard-table"}).text.strip() == "Report is 50% complete…"


@freeze_time("2016-01-01 11:09:00.061258")
@pytest.mark.skip(reason="feature not in use")
def test_should_show_letter_job(
    client_request,
    mock_get_service_letter_template,
    mock_get_job,
    mock_get_service_data_retention,
    fake_uuid,
    active_user_with_permissions,
    mocker,
):
    get_notifications = mock_get_notifications(mocker, active_user_with_permissions, diff_template_type="letter")

    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
    )
    assert normalize_spaces(page.h1.text) == "thisisatest.csv"
    assert normalize_spaces(page.select("p.mb-12.clear-both")[0].text) == (
        "Sent by Test User on 2016-01-01 11:09:00.061258 Printing starts today at 5:30pm"
    )
    assert page.select(".banner-default-with-tick") == []
    assert normalize_spaces(page.select("tbody tr")[0].text) == ("1 Example Street template subject 2016-01-01 11:09:00.061258")
    assert normalize_spaces(page.select(".keyline-block")[0].text) == ("1 Letter")
    assert normalize_spaces(page.select(".keyline-block")[1].text) == ("6 January Estimated delivery date")
    assert page.select("[download=download]") == []
    assert page.select(".hint") == []

    get_notifications.assert_called_with(
        SERVICE_ONE_ID,
        fake_uuid,
        status=[
            "created",
            "pending",
            "sending",
            "pending-virus-check",
            "delivered",
            "sent",
            "returned-letter",
            "failed",
            "temporary-failure",
            "permanent-failure",
            "technical-failure",
            "virus-scan-failed",
            "validation-failed",
        ],
    )


@freeze_time("2016-01-01 11:09:00")
@pytest.mark.skip(reason="feature not in use")
def test_should_show_letter_job_with_banner_after_sending_before_1730(
    client_request,
    mock_get_service_letter_template,
    mock_get_job,
    mock_get_notifications,
    mock_get_service_data_retention,
    fake_uuid,
):
    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
        just_sent="yes",
    )

    assert page.select("p.mb-12 clear-both") == []
    assert normalize_spaces(page.select(".banner-default-with-tick")[0].text) == (
        "Your letter has been sent. Printing starts today at 5:30pm."
    )


@freeze_time("2016-01-01 11:09:00")
@pytest.mark.skip(reason="feature not in use")
def test_should_show_letter_job_with_banner_when_there_are_multiple_CSV_rows(
    client_request,
    mock_get_service_letter_template,
    mock_get_job_in_progress,
    mock_get_notifications,
    mock_get_service_data_retention,
    fake_uuid,
):
    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
        just_sent="yes",
    )

    assert page.select("p.mb-12 clear-both") == []
    assert normalize_spaces(page.select(".banner-default-with-tick")[0].text) == (
        "Your letters have been sent. Printing starts today at 5:30pm."
    )


@freeze_time("2016-01-01 18:09:00")
@pytest.mark.skip(reason="feature not in use")
def test_should_show_letter_job_with_banner_after_sending_after_1730(
    client_request,
    mock_get_service_letter_template,
    mock_get_job,
    mock_get_notifications,
    mock_get_service_data_retention,
    fake_uuid,
):
    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
        just_sent="yes",
    )

    assert page.select("p.mb-12 clear-both") == []
    assert normalize_spaces(page.select(".banner-default-with-tick")[0].text) == (
        "Your letter has been sent. Printing starts tomorrow at 5:30pm."
    )


@freeze_time("2016-01-01T00:00:00.061258")
def test_should_show_scheduled_job(
    client_request,
    mock_get_service_template,
    mock_get_scheduled_job,
    mock_get_service_data_retention,
    mock_get_notifications,
    fake_uuid,
):
    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
    )

    scheduled_job = page.select("td > [class~='do-not-truncate-text']")
    assert normalize_spaces(scheduled_job[0]) == "Test User"
    assert normalize_spaces(scheduled_job[1]) == "2016-01-02T00:00:00.061258"
    assert normalize_spaces(scheduled_job[2]) == "thisisatest.csv"
    assert normalize_spaces(scheduled_job[3]) == "1 recipient(s)"
    assert page.select("td > a")[0]["href"] == url_for(
        "main.view_template_version",
        service_id=SERVICE_ONE_ID,
        template_id="5d729fbd-239c-44ab-b498-75a985f3198f",
        version=1,
    )
    assert page.select_one("button[type=submit]").text.strip() == "Cancel scheduled send"


@freeze_time("2016-01-01T00:00:00.061258")
def test_percent_complete_zero_if_job_is_scheduled_and_send_time_has_not_elapsed(
    client_request,
    mock_get_service_template,
    mock_get_scheduled_job,
    mock_get_service_data_retention,
    mock_get_no_notifications,
    fake_uuid,
):
    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
    )

    # These elements are not rendered if we're sending a scheduled job. Is also indicative of
    # percentage complete being 0 as notifications are not added to the DB until the time of send
    assert page.find(id="pe_filter") is None
    assert page.find("a[text='Download this report']") is None
    assert page.find("table") is None


@freeze_time("2016-01-01T00:00:00.061258")
def test_should_show_job_from_api(
    client_request,
    mock_get_service_template,
    mock_get_job_with_api_key,
    mock_get_service_data_retention,
    mock_get_notifications,
    fake_uuid,
):
    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
    )
    job_info_table = page.find_all("table")[0]

    assert normalize_spaces(job_info_table.select("th")[0].text) == "Sent by"
    assert normalize_spaces(job_info_table.select("td")[0].text) == f"API key '{JOB_API_KEY_NAME}'"

    assert normalize_spaces(job_info_table.select("th")[1].text) == "Started"
    assert normalize_spaces(job_info_table.select("td")[1].text) == "2016-01-01T00:00:00.061258+0000"


# TODO: This test could be migrated to Cypress instead
@freeze_time("2016-01-01T00:00:00.061258")
def test_should_show_scheduled_job_with_api_key(
    client_request,
    mock_get_service_template,
    mock_get_scheduled_job_with_api_key,
    mock_get_service_data_retention,
    mock_get_notifications,
    fake_uuid,
):
    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
    )
    scheduled_job = page.select("td > [class~='do-not-truncate-text']")
    assert normalize_spaces(scheduled_job[0].text) == f"API key '{JOB_API_KEY_NAME}'"
    assert normalize_spaces(scheduled_job[1]) == "2016-01-02T00:00:00.061258"
    assert normalize_spaces(scheduled_job[2]) == "thisisatest.csv"
    assert normalize_spaces(scheduled_job[3]) == "1 recipient(s)"
    assert page.select("td > a")[0]["href"] == url_for(
        "main.view_template_version",
        service_id=SERVICE_ONE_ID,
        template_id="5d729fbd-239c-44ab-b498-75a985f3198f",
        version=1,
    )

    assert page.select_one("button[type=submit]").text.strip() == "Cancel scheduled send"


def test_should_cancel_job(
    client_request,
    fake_uuid,
    mocker,
):
    mock_cancel = mocker.patch("app.main.jobs.job_api_client.cancel_job")
    client_request.post(
        "main.cancel_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
        _expected_status=302,
        _expected_redirect=url_for(
            "main.service_dashboard",
            service_id=SERVICE_ONE_ID,
        ),
    )

    mock_cancel.assert_called_once_with(SERVICE_ONE_ID, fake_uuid)


def test_should_not_show_cancelled_job(
    client_request,
    active_user_with_permissions,
    mock_get_cancelled_job,
    fake_uuid,
):
    client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
        _expected_status=404,
    )


def test_should_cancel_letter_job(client_request, mocker, active_user_with_permissions):
    job_id = uuid.uuid4()
    job = job_json(
        SERVICE_ONE_ID,
        active_user_with_permissions,
        job_id=job_id,
        created_at="2019-06-20T15:30:00.000001+00:00",
        job_status="finished",
    )
    mocker.patch("app.job_api_client.get_job", side_effect=[{"data": job}])
    notifications_json = notification_json(SERVICE_ONE_ID, job=job, status="created", template_type="letter")
    mocker.patch("app.job_api_client.get_job", side_effect=[{"data": job}])
    mocker.patch(
        "app.notification_api_client.get_notifications_for_service",
        side_effect=[notifications_json],
    )
    mock_cancel = mocker.patch("app.main.jobs.job_api_client.cancel_letter_job", return_value=5)
    client_request.post(
        "main.cancel_letter_job",
        service_id=SERVICE_ONE_ID,
        job_id=job_id,
        _expected_status=302,
        _expected_redirect=url_for(
            "main.service_dashboard",
            service_id=SERVICE_ONE_ID,
        ),
    )
    mock_cancel.assert_called_once_with(SERVICE_ONE_ID, job_id)


@freeze_time("2019-06-20 17:30:00.000001")
@pytest.mark.parametrize(
    "job_created_at, expected_fragment",
    [
        ("2019-06-20T15:30:00.000001+00:00", "today"),
        ("2019-06-19T15:30:00.000001+00:00", "yesterday"),
        ("2019-06-18T15:30:00.000001+00:00", "on 18 June"),
    ],
)
@pytest.mark.skip(reason="feature not in use")
def test_should_not_show_cancel_link_for_letter_job_if_too_late(
    client_request,
    mocker,
    mock_get_service_letter_template,
    mock_get_service_data_retention,
    active_user_with_permissions,
    job_created_at,
    expected_fragment,
):
    job_id = uuid.uuid4()
    job = job_json(
        SERVICE_ONE_ID,
        active_user_with_permissions,
        job_id=job_id,
        created_at=job_created_at,
    )
    notifications_json = notification_json(SERVICE_ONE_ID, job=job, status="created", template_type="letter")
    mocker.patch("app.job_api_client.get_job", side_effect=[{"data": job}])
    mocker.patch(
        "app.notification_api_client.get_notifications_for_service",
        side_effect=[notifications_json],
    )

    page = client_request.get("main.view_job", service_id=SERVICE_ONE_ID, job_id=str(job_id))

    assert "Cancel sending these letters" not in page
    assert page.find("p", {"id": "printing-info"}).text.strip() == "Printed {} at 5:30pm".format(expected_fragment)


@freeze_time("2019-06-20 15:32:00.000001")
@pytest.mark.skip(reason="feature not in use")
@pytest.mark.parametrize(" job_status", ["finished", "in progress"])
def test_should_show_cancel_link_for_letter_job(
    client_request,
    mocker,
    mock_get_service_letter_template,
    mock_get_service_data_retention,
    active_user_with_permissions,
    job_status,
):
    job_id = uuid.uuid4()
    job = job_json(
        SERVICE_ONE_ID,
        active_user_with_permissions,
        job_id=job_id,
        created_at="2019-06-20T15:30:00.000001+00:00",
        job_status=job_status,
    )
    notifications_json = notification_json(SERVICE_ONE_ID, job=job, status="created", template_type="letter")
    mocker.patch("app.job_api_client.get_job", side_effect=[{"data": job}])
    mocker.patch(
        "app.notification_api_client.get_notifications_for_service",
        side_effect=[notifications_json],
    )

    page = client_request.get("main.view_job", service_id=SERVICE_ONE_ID, job_id=str(job_id))

    assert page.find("a", text="Cancel sending these letters").attrs["href"] == url_for(
        "main.cancel_letter_job", service_id=SERVICE_ONE_ID, job_id=job_id
    )
    assert page.find("p", {"id": "printing-info"}).text.strip() == "Printing starts today at 5:30pm"


@freeze_time("2019-06-20 15:31:00.000001")
@pytest.mark.parametrize(
    "job_status,number_of_processed_notifications",
    [["in progress", 2], ["finished", 1]],
)
def test_dont_cancel_letter_job_when_to_early_to_cancel(
    client_request,
    mocker,
    mock_get_service_letter_template,
    mock_get_service_data_retention,
    active_user_with_permissions,
    job_status,
    number_of_processed_notifications,
):
    job_id = uuid.uuid4()
    job = job_json(
        SERVICE_ONE_ID,
        active_user_with_permissions,
        job_id=job_id,
        created_at="2019-06-20T15:30:00.000001+00:00",
        job_status=job_status,
        notification_count=2,
    )
    mocker.patch("app.job_api_client.get_job", side_effect=[{"data": job}, {"data": job}])

    notifications_json = notification_json(
        SERVICE_ONE_ID,
        job=job,
        status="created",
        template_type="letter",
        rows=number_of_processed_notifications,
    )
    mocker.patch(
        "app.notification_api_client.get_notifications_for_service",
        side_effect=[notifications_json, notifications_json],
    )

    mock_cancel = mocker.patch("app.main.jobs.job_api_client.cancel_letter_job")
    page = client_request.post(
        "main.cancel_letter_job",
        service_id=SERVICE_ONE_ID,
        job_id=str(job_id),
        _expected_status=200,
    )
    mock_cancel.assert_not_called()
    flash_message = normalize_spaces(page.find("div", class_="banner-dangerous").text)

    assert "We are still processing these letters, please try again in a minute." in flash_message


@freeze_time("2016-01-01 00:00:00.000001")
def test_should_show_updates_for_one_job_as_json(
    logged_in_client,
    service_one,
    active_user_with_permissions,
    mock_get_notifications,
    mock_get_service_template,
    mock_get_job,
    mock_get_service_data_retention,
    mocker,
    fake_uuid,
):
    response = logged_in_client.get(url_for("main.view_job_updates", service_id=service_one["id"], job_id=fake_uuid))

    assert response.status_code == 200
    content = json.loads(response.get_data(as_text=True))
    assert "sending" in content["counts"]
    assert "delivered" in content["counts"]
    assert "failed" in content["counts"]
    assert "Recipient" in content["notifications"]
    assert "6502532222" in content["notifications"]
    assert "Status" in content["notifications"]
    assert "Delivered" in content["notifications"]
    assert "00:01:00.000001" in content["notifications"]
    assert "2016-01-01T00:00:00.000001+0000" in content["status"]


@pytest.mark.parametrize(
    "job_created_at, expected_date",
    [
        ("2016-01-10 11:09:00.000000+00:00", "2016-01-18"),
        ("2016-01-04 11:09:00.000000+00:00", "2016-01-12"),
        ("2016-01-03 11:09:00.000000+00:00", "2016-01-11"),
        ("2016-01-02 23:59:59.000000+00:00", "2016-01-10"),
    ],
)
@freeze_time("2016-01-10 12:00:00.000000")
def test_available_until_datetime(job_created_at, expected_date):
    """We are putting a raw datetime string in the span, which later gets
    formatted by js on the client. That formatting doesn't exist in the
    python tests so this test checks the date part of the datetime string
    and checking is correct."""
    available_until_datetime = get_available_until_date(job_created_at)
    available_until_date = str(available_until_datetime).split(" ")[0]
    assert available_until_date == expected_date


@freeze_time("2016-01-01 11:09:00.061258")
@pytest.mark.skip(reason="feature not in use")
def test_should_show_letter_job_with_first_class_if_notifications_are_first_class(
    client_request,
    mock_get_service_letter_template,
    mock_get_job,
    mock_get_service_data_retention,
    fake_uuid,
    active_user_with_permissions,
    mocker,
):
    mock_get_notifications(
        mocker,
        active_user_with_permissions,
        diff_template_type="letter",
        postage="first",
    )

    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
    )

    assert normalize_spaces(page.select(".keyline-block")[1].text) == "5 January Estimated delivery date"


@freeze_time("2016-01-01 11:09:00.061258")
def test_should_show_letter_job_with_first_class_if_no_notifications(
    client_request,
    service_one,
    mock_get_job,
    fake_uuid,
    mock_get_notifications_with_no_notifications,
    mock_get_service_data_retention,
    mocker,
):
    mocker.patch(
        "app.service_api_client.get_service_template",
        return_value=create_template(template_type="letter", postage="first"),
    )

    page = client_request.get(
        "main.view_job",
        service_id=SERVICE_ONE_ID,
        job_id=fake_uuid,
    )

    assert normalize_spaces(page.select(".keyline-block")[1].text) == "5 January Estimated delivery date"


def test_a11y_ensure_headings_are_hidden_when_no_data_on_view_job_page(
    client_request,
    fake_uuid,
    service_one,
    mock_get_job,
    mock_get_service_template,
    mock_get_no_notifications,
    mock_get_service_data_retention,
):
    page = client_request.get(
        "main.view_job",
        service_id=service_one["id"],
        job_id=fake_uuid,
        status="sending",
    )
    assert len(page.find_all("thead", {"class": "table-field-headings-visible"})) == 0
    assert len(page.find_all("thead", {"class": "table-field-headings"})) == 1


class TestBounceRate:
    def test_jobs_page_shows_problem_email_filter(
        self,
        client_request,
        active_user_with_permissions,
        mock_get_service_template,
        mock_get_job,
        mocker,
        mock_get_notifications,
        mock_get_service_data_retention,
        fake_uuid,
        app_,
    ):
        page = client_request.get(
            "main.view_job",
            service_id=SERVICE_ONE_ID,
            job_id=fake_uuid,
        )

        assert len(page.find(id="pe_filter")) is not None
