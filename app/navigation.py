from itertools import chain

from flask import request


class Navigation:
    mapping: dict = {}
    exclude: set = set()
    selected_attribute = "class=selected"

    def __init__(self):
        self.mapping = {
            navigation: {"main.{}".format(endpoint) for endpoint in endpoints} for navigation, endpoints in self.mapping.items()
        }

    @property
    def endpoints_with_navigation(self):
        return tuple(chain.from_iterable((endpoints for navigation_item, endpoints in self.mapping.items())))

    @property
    def endpoints_without_navigation(self):
        return tuple("main.{}".format(endpoint) for endpoint in self.exclude) + ("static", "status.show_status", "status.debug")

    def is_selected(self, navigation_item):
        if request.endpoint in self.mapping[navigation_item]:
            return self.selected_attribute
        return ""


class AdminNavigation(Navigation):
    selected_attribute = "active"

    mapping = {
        "choose_account": {
            "choose_account",
        },
        "live_services": {
            "live_services",
        },
        "trial_services": {
            "trial_services",
        },
        "organisations": {
            "organisations",
        },
        "live_api_keys": {
            "live_api_keys",
        },
        "email_branding": {
            "email_branding",
        },
        "template_categories": {
            "template_categories",
            "template_category",
        },
        "find_services_by_name": {
            "find_services_by_name",
        },
        "find_users_by_email": {
            "find_users_by_email",
        },
        "platform_admin_list_complaints": {
            "platform_admin_list_complaints",
        },
        "platform_admin_reports": {
            "platform_admin_reports",
        },
        "inbound_sms_admin": {
            "inbound_sms_admin",
        },
        "view_providers": {
            "view_providers",
        },
        "clear_cache": {
            "clear_cache",
        },
    }


class HeaderNavigation(Navigation):
    selected_attribute = "active"

    mapping = {
        "dashboard": {
            "monthly",
            "service_dashboard",
            "template_usage",
            "view_job",
            "view_jobs",
            "view_notification",
            "view_notifications",
        },
        "support": {
            "set_lang",
            "contact",
        },
        "features": {
            "features",
        },
        "home": {
            "index",
        },
        "why-notify": {
            "why-notify",
        },
        "contact": {
            "contact",
        },
        "pricing": {
            "pricing",
        },
        "documentation": {
            "documentation",
        },
        "design_content": {
            "design_content",
        },
        "user-profile": {
            "user_profile",
            "user_profile_email",
            "user_profile_email_authenticate",
            "user_profile_email_confirm",
            "user_profile_mobile_number",
            "user_profile_mobile_number_authenticate",
            "user_profile_mobile_number_confirm",
            "user_profile_name",
            "user_profile_password",
            "user_profile_disable_platform_admin_view",
        },
        "sign-in": {
            "sign_in",
            "two_factor_sms_sent",
            "two_factor_email_sent",
            "verify",
            "verify_email",
            "verify_mobile",
        },
        "choose_account": {
            "choose_account",
        },
        "team-members": {
            "confirm_edit_user_email",
            "confirm_edit_user_mobile_number",
            "edit_user_email",
            "edit_user_mobile_number",
            "edit_user_permissions",
            "invite_user",
            "manage_users",
            "remove_user_from_service",
        },
        "templates": {
            "action_blocked",
            "add_recipients",
            "add_service_template",
            "check_messages",
            "check_notification",
            "choose_template",
            "choose_template_to_copy",
            "confirm_redact_template",
            "copy_template",
            "delete_service_template",
            "edit_service_template",
            "edit_template_postage",
            "manage_template_folder",
            "s3_send",
            "send_messages",
            "send_one_off",
            "send_one_off_step",
            "send_test",
            "send_test_preview",
            "send_test_step",
            "set_sender",
            "set_template_sender",
            "preview_template",
            "view_template",
            "view_template_version",
            "view_template_versions",
        },
        "api-integration": {
            "api_callbacks",
            "api_documentation",
            "api_integration",
            "api_keys",
            "create_api_key",
            "delivery_status_callback",
            "received_text_messages_callback",
            "revoke_api_key",
            "safelist",
        },
        "settings": {
            "branding_request",
            "link_service_to_organisation",
            "request_letter_branding",
            "request_to_go_live",
            "service_add_email_reply_to",
            "service_add_letter_contact",
            "service_add_sms_sender",
            "service_confirm_delete_email_reply_to",
            "service_confirm_delete_letter_contact",
            "service_confirm_delete_sms_sender",
            "service_edit_email_reply_to",
            "service_edit_letter_contact",
            "service_edit_sms_sender",
            "service_email_reply_to",
            "service_letter_contact_details",
            "service_make_blank_default_letter_contact",
            "service_name_change",
            "service_name_change_confirm",
            "service_email_from_change",
            "service_email_from_change_confirm",
            "service_preview_email_branding",
            "service_preview_letter_branding",
            "service_set_auth_type",
            "service_set_channel",
            "service_set_contact_link",
            "service_set_email_branding",
            "service_set_inbound_number",
            "service_set_inbound_sms",
            "service_set_international_sms",
            "service_set_letter_contact_block",
            "service_set_letters",
            "service_set_reply_to_email",
            "service_set_sms_prefix",
            "service_verify_reply_to_address",
            "service_verify_reply_to_address_updates",
            "service_settings",
            "service_sms_senders",
            "set_message_limit",
            "set_free_sms_allowance",
            "service_set_letter_branding",
            "submit_request_to_go_live",
        },
        "sent-messages": {
            "view_notifications",
            "view_notification",
        },
        "bulk-sends": {
            "view_jobs",
            "view_job",
        },
    }

    exclude = {
        "accept_invite",
        "accept_org_invite",
        "add_data_retention",
        "add_inbound_sms_admin",
        "add_organisation",
        "add_service",
        "archive_service",
        "callbacks",
        "cancel_invited_org_user",
        "cancel_invited_user",
        "cancel_job",
        "cancel_letter",
        "cancel_letter_job",
        "check_and_resend_text_code",
        "check_and_resend_verification_code",
        "check_messages_preview",
        "check_notification_preview",
        "choose_account",
        "choose_service",
        "confirm_edit_organisation_name",
        "data_retention",
        "delete_template_folder",
        "design_content",
        "download_notifications_csv",
        "edit_data_retention",
        "edit_organisation_agreement",
        "edit_organisation_crown_status",
        "edit_organisation_domains",
        "edit_organisation_email_branding",
        "edit_organisation_letter_branding",
        "edit_organisation_go_live_notes",
        "edit_organisation_name",
        "edit_organisation_type",
        "edit_provider",
        "edit_user_org_permissions",
        "email_not_received",
        "email_template",
        "error",
        "forgot_password",
        "forced-password-reset",
        "get_example_csv",
        "get_notifications_as_json",
        "go_to_dashboard_after_tour",
        "inbound_sms_admin",
        "invite_org_user",
        "letter_branding_preview_image",
        "letter_template",
        "manage_org_users",
        "new_password",
        "redirect_contact",
        "redirect_service_dashboard",
        "redirect_terms",
        "redirect_roadmap",
        "redirect_email",
        "redirect_sms",
        "redirect_letters",
        "redirect_templates",
        "redirect_security",
        "redirect_messages_status",
        "organisation_dashboard",
        "organisation_trial_mode_services",
        "organisation_settings",
        "organisation_preview_email_branding",
        "organisation_preview_letter_branding",
        "organisations",
        "privacy",
        "redact_template",
        "register",
        "register_from_invite",
        "register_from_org_invite",
        "registration_continue",
        "remove_user_from_organisation",
        "remove_user_from_service",
        "request_letter_branding",
        "request_to_go_live",
        "terms_of_use",
        "use_case",
        "resend_email_link",
        "resend_email_verification",
        "resume_service",
        "robots",
        "security_txt",
        "send_notification",
        "service_dashboard",
        "service_dashboard_updates",
        "service_delete_email_reply_to",
        "service_delete_letter_contact",
        "service_delete_sms_sender",
        "service_letter_validation_preview",
        "service_switch_upload_document",
        "service_switch_count_as_live",
        "service_switch_live",
        "service_set_permission",
        "services_or_dashboard",
        "show_accounts_or_dashboard",
        "sign_out",
        "start_job",
        "start_tour",
        "styleguide",
        "temp_service_history",
        "template_history",
        "user_profile_authenticate_security_keys",
        "user_profile_complete_security_keys",
        "user_profile_validate_security_keys",
        "user_profile_add_security_keys",
        "user_profile_security_keys",
        "user_profile_security_keys_confirm_delete",
        "uploads",
        "usage",
        "view_job_csv",
        "view_job_updates",
        "view_letter_notification_as_preview",
        "view_letter_template_preview",
        "view_notification_updates",
        "view_notifications_csv",
        "view_template_version_preview",
        "safelist",
        "get_template_data",
        "block_user",
        "unblock_user",
        "service_sending_domain",
        "welcome",
    }


class MainNavigation(Navigation):
    mapping = {
        "dashboard": {
            "problem_emails",
            "monthly",
            "service_dashboard",
            "template_usage",
            "view_job",
            "view_jobs",
            "view_notification",
            "view_notifications",
        },
        "templates": {
            "action_blocked",
            "add_service_template",
            "check_messages",
            "check_notification",
            "choose_template",
            "choose_template_to_copy",
            "confirm_redact_template",
            "copy_template",
            "delete_service_template",
            "edit_service_template",
            "edit_template_postage",
            "manage_template_folder",
            "s3_send",
            "send_messages",
            "send_one_off",
            "send_one_off_step",
            "send_test",
            "send_test_preview",
            "send_test_step",
            "set_sender",
            "set_template_sender",
            "view_template",
            "view_template_version",
            "view_template_versions",
            "welcome",
        },
        "uploads": {
            "uploads",
        },
        "team-members": {
            "confirm_edit_user_email",
            "confirm_edit_user_mobile_number",
            "edit_user_email",
            "edit_user_mobile_number",
            "edit_user_permissions",
            "invite_user",
            "manage_users",
            "remove_user_from_service",
        },
        "usage": {
            "usage",
        },
        "contact": {"message", "demo_organization_details", "demo_primary_purpose"},
        "settings": {
            "branding_request",
            "link_service_to_organisation",
            "request_letter_branding",
            "request_to_go_live",
            "terms_of_use",
            "use_case",
            "service_add_email_reply_to",
            "service_add_letter_contact",
            "service_add_sms_sender",
            "service_confirm_delete_email_reply_to",
            "service_confirm_delete_letter_contact",
            "service_confirm_delete_sms_sender",
            "service_edit_email_reply_to",
            "service_edit_letter_contact",
            "service_edit_sms_sender",
            "service_email_reply_to",
            "service_letter_contact_details",
            "service_make_blank_default_letter_contact",
            "service_name_change",
            "service_name_change_confirm",
            "service_email_from_change",
            "service_email_from_change_confirm",
            "service_preview_email_branding",
            "service_preview_letter_branding",
            "service_set_auth_type",
            "service_set_channel",
            "service_set_contact_link",
            "service_set_email_branding",
            "service_set_inbound_number",
            "service_set_inbound_sms",
            "service_set_international_sms",
            "service_set_letter_contact_block",
            "service_set_letters",
            "service_set_reply_to_email",
            "service_set_sms_prefix",
            "service_verify_reply_to_address",
            "service_verify_reply_to_address_updates",
            "service_settings",
            "service_sms_senders",
            "set_message_limit",
            "set_free_sms_allowance",
            "service_set_letter_branding",
            "submit_request_to_go_live",
        },
        "api-integration": {
            "api_callbacks",
            "api_documentation",
            "api_integration",
            "api_keys",
            "create_api_key",
            "delivery_status_callback",
            "received_text_messages_callback",
            "revoke_api_key",
            "safelist",
        },
        "choose_account": {
            "choose_account",
        },
        "live_services": {
            "live_services",
        },
        "user_profile": {
            "user_profile",
        },
        "sign_out": {"sign_out"},
    }

    exclude = {
        "accept_invite",
        "accept_org_invite",
        "add_data_retention",
        "add_inbound_sms_admin",
        "add_organisation",
        "add_service",
        "archive_service",
        "archive_user",
        "clear_cache",
        "create_email_branding",
        "create_letter_branding",
        "email_branding",
        "template_categories",
        "find_services_by_name",
        "find_users_by_email",
        "letter_branding",
        "live_api_keys",
        "live_services",
        "live_services_csv",
        "notifications_sent_by_service",
        "performance_platform_xlsx",
        "send_method_stats_by_service",
        "trial_report_csv",
        "usage_for_all_services",
        "platform_admin",
        "platform_admin_letter_validation_preview",
        "platform_admin_list_complaints",
        "platform_admin_reports",
        "platform_admin_returned_letters",
        "suspend_service",
        "trial_services",
        "update_email_branding",
        "update_letter_branding",
        "user_information",
        "view_provider",
        "view_providers",
        "welcome",
    }


class OrgNavigation(Navigation):
    mapping = {
        "dashboard": {
            "organisation_dashboard",
        },
        "settings": {
            "confirm_edit_organisation_name",
            "edit_organisation_agreement",
            "edit_organisation_crown_status",
            "edit_organisation_domains",
            "edit_organisation_email_branding",
            "edit_organisation_letter_branding",
            "edit_organisation_domains",
            "edit_organisation_go_live_notes",
            "edit_organisation_name",
            "edit_organisation_type",
            "organisation_preview_email_branding",
            "organisation_preview_letter_branding",
            "organisation_settings",
        },
        "team-members": {
            "edit_user_org_permissions",
            "invite_org_user",
            "manage_org_users",
            "remove_user_from_organisation",
        },
        "trial-services": {
            "organisation_trial_mode_services",
        },
    }

    exclude = {
        "accept_invite",
        "accept_org_invite",
        "a11y",
        "action_blocked",
        "add_data_retention",
        "add_inbound_sms_admin",
        "add_organisation",
        "add_service",
        "add_service_template",
        "api_callbacks",
        "api_documentation",
        "api_integration",
        "api_keys",
        "archive_service",
        "archive_user",
        "branding_request",
        "callbacks",
        "cancel_invited_org_user",
        "cancel_invited_user",
        "cancel_job",
        "cancel_letter",
        "cancel_letter_job",
        "check_and_resend_text_code",
        "check_and_resend_verification_code",
        "check_messages",
        "check_messages_preview",
        "check_notification",
        "check_notification_preview",
        "choose_account",
        "choose_service",
        "choose_template",
        "choose_template_to_copy",
        "clear_cache",
        "confirm_edit_user_email",
        "confirm_edit_user_mobile_number",
        "confirm_redact_template",
        "copy_template",
        "create_api_key",
        "create_email_branding",
        "create_letter_branding",
        "data_retention",
        "delete_service_template",
        "delete_template_folder",
        "delivery_status_callback",
        "design_content",
        "documentation",
        "download_notifications_csv",
        "edit_data_retention",
        "edit_provider",
        "edit_service_template",
        "edit_template_postage",
        "edit_user_email",
        "edit_user_mobile_number",
        "edit_user_permissions",
        "email_branding",
        "template_categories",
        "email_not_received",
        "email_template",
        "error",
        "features",
        "email",
        "letters",
        "templates",
        "sms",
        "contact",
        "find_services_by_name",
        "find_users_by_email",
        "forgot_password",
        "forced-password-reset",
        "get_example_csv",
        "get_notifications_as_json",
        "go_to_dashboard_after_tour",
        "inbound_sms_admin",
        "index",
        "invite_user",
        "letter_branding",
        "letter_branding_preview_image",
        "letter_template",
        "link_service_to_organisation",
        "live_api_keys",
        "live_services",
        "live_services_csv",
        "manage_template_folder",
        "manage_users",
        "messages_status",
        "new_password",
        "notifications_sent_by_service",
        "redirect_contact",
        "redirect_roadmap",
        "redirect_service_dashboard",
        "redirect_terms",
        "redirect_email",
        "redirect_sms",
        "redirect_letters",
        "redirect_templates",
        "redirect_security",
        "redirect_messages_status",
        "organisations",
        "performance_platform_xlsx",
        "send_method_stats_by_service",
        "trial_report_csv",
        "platform_admin",
        "platform_admin_letter_validation_preview",
        "platform_admin_list_complaints",
        "platform_admin_reports",
        "platform_admin_returned_letters",
        "pricing",
        "privacy",
        "received_text_messages_callback",
        "redact_template",
        "register",
        "register_from_invite",
        "register_from_org_invite",
        "registration_continue",
        "remove_user_from_service",
        "request_letter_branding",
        "request_to_go_live",
        "terms_of_use",
        "use_case",
        "resend_email_link",
        "resend_email_verification",
        "resume_service",
        "revoke_api_key",
        "roadmap",
        "robots",
        "s3_send",
        "security",
        "security_txt",
        "send_messages",
        "send_notification",
        "send_one_off",
        "send_one_off_step",
        "send_test",
        "send_test_preview",
        "send_test_step",
        "service_add_email_reply_to",
        "service_add_letter_contact",
        "service_add_sms_sender",
        "service_confirm_delete_email_reply_to",
        "service_confirm_delete_letter_contact",
        "service_confirm_delete_sms_sender",
        "service_dashboard",
        "service_dashboard_updates",
        "service_delete_email_reply_to",
        "service_delete_letter_contact",
        "service_delete_sms_sender",
        "service_edit_email_reply_to",
        "service_edit_letter_contact",
        "service_edit_sms_sender",
        "service_email_reply_to",
        "service_letter_contact_details",
        "service_letter_validation_preview",
        "service_make_blank_default_letter_contact",
        "service_name_change",
        "service_name_change_confirm",
        "service_email_from_change",
        "service_email_from_change_confirm",
        "service_preview_email_branding",
        "service_preview_letter_branding",
        "service_set_auth_type",
        "service_set_channel",
        "service_set_contact_link",
        "service_set_email_branding",
        "service_set_inbound_number",
        "service_set_inbound_sms",
        "service_set_international_sms",
        "service_set_letter_contact_block",
        "service_set_letters",
        "service_set_reply_to_email",
        "service_set_sms_prefix",
        "service_settings",
        "service_sms_senders",
        "service_switch_upload_document",
        "service_switch_count_as_live",
        "service_switch_live",
        "service_set_permission",
        "service_verify_reply_to_address",
        "service_verify_reply_to_address_updates",
        "services_or_dashboard",
        "set_message_limit",
        "set_free_sms_allowance",
        "service_set_letter_branding",
        "set_lang",
        "set_sender",
        "set_template_sender",
        "show_accounts_or_dashboard",
        "sign_in",
        "sign_out",
        "start_job",
        "start_tour",
        "activity",
        "activity_download",
        "styleguide",
        "submit_request_to_go_live",
        "suspend_service",
        "temp_service_history",
        "template_history",
        "template_usage",
        "terms",
        "trial_services",
        "two_factor_sms_sent",
        "two_factor_email_sent",
        "update_email_branding",
        "update_letter_branding",
        "uploads",
        "usage",
        "usage_for_all_services",
        "user_information",
        "user_profile",
        "user_profile_authenticate_security_keys",
        "user_profile_complete_security_keys",
        "user_profile_validate_security_keys",
        "user_profile_add_security_keys",
        "user_profile_security_keys",
        "user_profile_security_keys_confirm_delete",
        "user_profile_email",
        "user_profile_email_authenticate",
        "user_profile_email_confirm",
        "user_profile_mobile_number",
        "user_profile_mobile_number_authenticate",
        "user_profile_mobile_number_confirm",
        "user_profile_name",
        "user_profile_password",
        "user_profile_disable_platform_admin_view",
        "verify",
        "verify_email",
        "verify_mobile",
        "view_job",
        "view_job_csv",
        "view_job_updates",
        "view_jobs",
        "view_letter_notification_as_preview",
        "view_letter_template_preview",
        "view_notification",
        "view_notification_updates",
        "view_notifications",
        "view_notifications_csv",
        "view_provider",
        "view_providers",
        "view_template",
        "view_template_version",
        "view_template_version_preview",
        "view_template_versions",
        "why-notify",
        "safelist",
        "get_template_data",
        "block_user",
        "unblock_user",
        "service_sending_domain",
        "welcome",
    }
