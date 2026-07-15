from django.urls import path

from . import views

urlpatterns = [
    # Template views
    path("", views.index_page, name="index"),
    path("register/", views.register_page, name="register-page"),
    path("login/", views.login_page, name="login-page"),
    path("dashboard/", views.dashboard_page, name="dashboard-page"),
    path("admin-dashboard/", views.admin_dashboard_page, name="admin-dashboard-page"),

    # Auth API
    path("api/auth/register", views.register_api, name="register-api"),
    path("api/auth/login", views.login_api, name="login-api"),
    path("api/auth/logout", views.logout_api, name="logout-api"),
    path("api/auth/me", views.me_api, name="me-api"),
    path("api/profile/update", views.update_profile_api, name="update-profile-api"),
    path("api/debug/headers", views.debug_headers_api, name="debug-headers-api"),

    # Verification API
    path("api/verification/submit", views.submit_verification_api, name="verification-submit-api"),
    path("api/verification/status", views.verification_status_api, name="verification-status-api"),

    # Projects API
    path("api/projects", views.projects_api, name="projects-api"),

    # Bids API
    path("api/bids/place", views.place_bid_api, name="place-bid-api"),
    path("api/bids/my", views.my_bids_api, name="my-bids-api"),
    path("api/bids/all", views.all_bids_api, name="all-bids-api"),
    path("api/bids/<int:bid_id>/status", views.bid_status_update_api, name="bid-status-update-api"),

    # Assignments API
    path("api/assignments/my", views.my_assignments_api, name="my-assignments-api"),
    path("api/assignments/<int:assignment_id>/submit", views.submit_deliverable_api, name="submit-deliverable-api"),
    path("api/assignments/<int:assignment_id>/review", views.review_assignment_api, name="review-assignment-api"),

    # Earnings / Transactions / Withdrawals
    path("api/earnings", views.earnings_api, name="earnings-api"),
    path("api/withdraw/request", views.create_withdraw_request_api, name="withdraw-request-api"),
    path("api/withdraw/my", views.my_withdraw_requests_api, name="my-withdraw-api"),

    # System Mails
    path("api/mails", views.user_mails_api, name="user-mails-api"),
    path("api/mails/<int:mail_id>/read", views.mark_mail_read_api, name="mark-mail-read-api"),
    path("api/mails/read-all", views.mark_all_mails_read_api, name="mark-all-mails-read-api"),

    # Admin
    path("api/admin/pending-users", views.admin_pending_users_api, name="admin-pending-users-api"),
    path("api/admin/verify-user", views.admin_verify_user_api, name="admin-verify-user-api"),
    path("api/admin/users/<int:user_id>/approve", views.admin_approve_user_api, name="admin-approve-user-api"),
    path("api/admin/users/<int:user_id>/reject", views.admin_reject_user_api, name="admin-reject-user-api"),
    path("api/admin/withdrawals", views.admin_all_withdrawals_api, name="admin-all-withdrawals-api"),
    path("api/admin/withdrawals/<int:withdraw_id>/process", views.admin_process_withdrawal_api, name="admin-process-withdrawal-api"),
]

