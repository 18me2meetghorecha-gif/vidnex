import base64
from decimal import Decimal

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.authentication import BaseAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response

from .models import (
    Assignment,
    Bid,
    Earning,
    NEXT_ALLOWED_STATUSES,
    Project,
    SystemMail,
    Transaction as TxnModel,
    VerificationDetail,
    WithdrawRequest,
)
from .serializers import (
    AssignmentSerializer,
    BidCreateSerializer,
    BidSerializer,
    BidStatusUpdateSerializer,
    DeliverableSubmitSerializer,
    EarningsSerializer,
    LoginSerializer,
    MeSerializer,
    PendingUserSerializer,
    ProjectSerializer,
    RegisterSerializer,
    ReviewSerializer,
    SystemMailSerializer,
    TransactionSerializer,
    UpdateProfileSerializer,
    VerificationDetailSerializer,
    VerificationSubmitSerializer,
    WithdrawRequestSerializer,
    WithdrawSerializer,
)


# ---------------------------------------------------------------------------
# Custom authentication: accepts token via X-Auth-Token header
# (Railway's edge proxy strips the standard Authorization header)
# ---------------------------------------------------------------------------

class XTokenAuthentication(BaseAuthentication):
    """Read token from X-Auth-Token header as Railway strips Authorization."""

    def authenticate(self, request):
        raw = request.META.get("HTTP_X_AUTH_TOKEN", "").strip()
        if not raw:
            # Also accept standard Authorization: Token xxx as fallback
            auth = request.META.get("HTTP_AUTHORIZATION", "").strip()
            if auth.lower().startswith("token "):
                raw = auth[6:].strip()
        if not raw:
            return None
        try:
            token_obj = Token.objects.select_related("user").get(key=raw)
        except Token.DoesNotExist:
            raise AuthenticationFailed("Invalid or expired token.")
        if not token_obj.user.is_active:
            raise AuthenticationFailed("User account is disabled.")
        return (token_obj.user, token_obj)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_admin(user):
    return user.is_authenticated and hasattr(user, "profile") and user.profile.role == "admin"


def _send_mail(user, subject, body, event=""):
    """Create an in-app system mail (and optionally a real email via Django backend)."""
    SystemMail.objects.create(user=user, subject=subject, body=body, event=event)


def _decode_base64_file(data_url, filename):
    """Convert a base64 data URL into a Django ContentFile."""
    try:
        if "," in data_url:
            _, encoded = data_url.split(",", 1)
        else:
            encoded = data_url
        return ContentFile(base64.b64decode(encoded), name=filename)
    except Exception:
        return None


def _ensure_seed_projects():
    if Project.objects.count() > 0:
        return
    Project.objects.bulk_create([
        Project(
            title="AI Defect Detection for Manufacturing Line",
            category="Artificial Intelligence",
            description="Build an ML model to detect defects from conveyor camera data in real-time. Deliverables include a trained model, evaluation report, and API integration guide.",
            min_budget=Decimal("35000.00"),
            max_budget=Decimal("90000.00"),
            default_timeline="10 weeks",
        ),
        Project(
            title="Low-cost Composite Material Optimization",
            category="Materials Science",
            description="Suggest and validate material combinations for improved heat resistance in industrial settings. Deliverables include material test data and a recommendations report.",
            min_budget=Decimal("25000.00"),
            max_budget=Decimal("70000.00"),
            default_timeline="8 weeks",
        ),
        Project(
            title="Energy Optimization in Plant Operations",
            category="Industrial Engineering",
            description="Identify process interventions to reduce electricity usage by at least 12%. Deliverables include energy audit, simulations, and an implementation roadmap.",
            min_budget=Decimal("40000.00"),
            max_budget=Decimal("120000.00"),
            default_timeline="12 weeks",
        ),
    ])


def _build_me_data(user):
    profile = user.profile
    vdetails = getattr(user, "verification", None)
    researcher_details = None
    if vdetails:
        researcher_details = {
            "work_company": vdetails.work_company,
            "work_role": vdetails.work_role,
            "work_years": vdetails.work_years,
            "education_degree": vdetails.education_degree,
            "education_university": vdetails.education_university,
            "education_year": vdetails.education_year,
        }
    return {
        "id": user.id,
        "email": user.email,
        "full_name": profile.full_name,
        "role": profile.role,
        "status": profile.status,
        "rejection_reason": profile.rejection_reason or "",
        "bio": profile.bio or "",
        "phone": profile.phone or "",
        "created_at": profile.created_at,
        "researcher_details": researcher_details,
    }


# ---------------------------------------------------------------------------
# Template views (for Django-rendered pages, kept for admin panel)
# ---------------------------------------------------------------------------

def index_page(request):
    return render(request, "core/home.html")


def register_page(request):
    return render(request, "core/register.html")


def login_page(request):
    return render(request, "core/login.html")


def dashboard_page(request):
    return render(request, "core/dashboard.html")


def admin_dashboard_page(request):
    return render(request, "core/admin_dashboard.html")


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def debug_headers_api(request):
    """Temporary: show which HTTP headers reach Django (Railway proxy diagnostic)."""
    relevant = {
        k.replace("HTTP_", "").replace("_", "-").title(): v
        for k, v in request.META.items()
        if k.startswith("HTTP_") and any(
            x in k for x in ["AUTHOR", "X_AUTH", "TOKEN", "COOKIE", "HOST", "ORIGIN"]
        )
    }
    # Also test token lookup directly
    x_token = request.META.get("HTTP_X_AUTH_TOKEN", "").strip()
    auth_hdr = request.META.get("HTTP_AUTHORIZATION", "").strip()
    raw = x_token or (auth_hdr[6:].strip() if auth_hdr.lower().startswith("token ") else "")
    token_exists = False
    token_user = None
    if raw:
        try:
            tok = Token.objects.select_related("user").get(key=raw)
            token_exists = True
            token_user = tok.user.email
        except Token.DoesNotExist:
            pass
    return Response({
        "received_headers": relevant,
        "token_raw": raw[:8] + "..." if raw else None,
        "token_in_db": token_exists,
        "token_user": token_user,
    })


# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register_api(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    email = data["email"].lower()

    with transaction.atomic():
        user = User.objects.create_user(
            username=email,
            email=email,
            password=data["password"],
        )
        user.first_name = data["full_name"]
        user.save()

        profile = user.profile
        profile.full_name = data["full_name"]
        profile.role = data.get("role", "researcher")
        profile.status = "pending_verification"
        profile.save()

        Earning.objects.get_or_create(user=user)

    _send_mail(
        user,
        subject="Welcome to Vidnex!",
        body="Hi {},\n\nYour account has been created. Please submit your verification details to get started.".format(profile.full_name),
        event="registration",
    )

    return Response(
        {"message": "Registration successful. Please log in and complete verification.", "status": profile.status},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login_api(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"].lower()
    password = serializer.validated_data["password"]

    user = authenticate(request, username=email, password=password)
    if not user:
        return Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

    login(request, user)
    token, _ = Token.objects.get_or_create(user=user)
    me = _build_me_data(user)
    me["token"] = token.key
    return Response(me)


@api_view(["POST"])
def logout_api(request):
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    logout(request)
    return Response({"message": "Logged out."})


@api_view(["GET"])
def me_api(request):
    data = _build_me_data(request.user)
    serializer = MeSerializer(data)
    return Response(serializer.data)


@api_view(["POST"])
def update_profile_api(request):
    serializer = UpdateProfileSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    profile = request.user.profile
    if "bio" in serializer.validated_data:
        profile.bio = serializer.validated_data["bio"]
    if "phone" in serializer.validated_data:
        profile.phone = serializer.validated_data["phone"]
    profile.save()

    return Response({"message": "Profile updated.", **_build_me_data(request.user)})


# ---------------------------------------------------------------------------
# Verification API
# ---------------------------------------------------------------------------

@api_view(["POST"])
def submit_verification_api(request):
    profile = request.user.profile
    if profile.role == "admin":
        return Response({"detail": "Admin accounts do not require verification."}, status=status.HTTP_403_FORBIDDEN)

    serializer = VerificationSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data

    resume_file = serializer._decode_file(d["resume_data"], d["resume_name"])
    cert_data = d.get("certificate_data", "")
    cert_name = d.get("certificate_name", "none")
    cert_file = serializer._decode_file(cert_data, cert_name) if cert_data and cert_name not in ("", "none") else None
    id_file = serializer._decode_file(d["id_proof_data"], d["id_proof_name"])

    vdetails, _ = VerificationDetail.objects.get_or_create(
        user=request.user,
        defaults={"work_company": "", "work_role": "", "work_years": 0,
                  "education_degree": "", "education_university": "", "education_year": 2000},
    )
    vdetails.work_company = d["work_company"]
    vdetails.work_role = d["work_role"]
    vdetails.work_years = d["work_years"]
    vdetails.education_degree = d["education_degree"]
    vdetails.education_university = d["education_university"]
    vdetails.education_year = d["education_year"]

    if resume_file:
        vdetails.resume.save(d["resume_name"], resume_file, save=False)
    if cert_file:
        vdetails.certificates.save(d["certificate_name"], cert_file, save=False)
    if id_file:
        vdetails.id_proof.save(d["id_proof_name"], id_file, save=False)

    vdetails.save()

    profile.status = "pending_verification"
    profile.rejection_reason = ""
    profile.save()

    return Response({
        "message": "Verification details submitted. Please wait for admin review.",
        "status": profile.status,
    })


@api_view(["GET"])
def verification_status_api(request):
    profile = request.user.profile
    vdetails = getattr(request.user, "verification", None)
    return Response({
        "status": profile.status,
        "rejection_reason": profile.rejection_reason or "",
        "submitted": bool(vdetails),
        "details": VerificationDetailSerializer(vdetails).data if vdetails else None,
    })


# ---------------------------------------------------------------------------
# Projects API
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def projects_api(request):
    _ensure_seed_projects()
    projects = Project.objects.filter(active=True).order_by("-created_at")
    return Response(ProjectSerializer(projects, many=True).data)


# ---------------------------------------------------------------------------
# Bids API
# ---------------------------------------------------------------------------

@api_view(["POST"])
def place_bid_api(request):
    profile = request.user.profile
    if profile.status != "verified":
        return Response({"detail": "Your account must be verified to place bids."}, status=status.HTTP_403_FORBIDDEN)

    serializer = BidCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data

    project = get_object_or_404(Project, id=d["project_id"], active=True)

    # Cannot re-bid on rejected/completed projects
    existing = Bid.objects.filter(user=request.user, project=project).first()
    if existing and existing.status in ("allocated", "in_progress", "submitted", "completed"):
        return Response({"detail": "Cannot modify a bid that is already in progress."}, status=status.HTTP_400_BAD_REQUEST)

    bid, created = Bid.objects.update_or_create(
        user=request.user,
        project=project,
        defaults={
            "amount": d["amount"],
            "proposal_note": d.get("proposal_note", ""),
            "status": "pending",
        },
    )

    _send_mail(
        request.user,
        subject="Bid {} on \"{}\"".format("placed" if created else "updated", project.title),
        body="Your bid of INR {:,.0f} has been {} on project: {}.".format(d["amount"], "placed" if created else "updated", project.title),
        event="bid_placed",
    )

    return Response({
        "message": "Bid {} successfully.".format("placed" if created else "updated"),
        "bid": BidSerializer(bid).data,
    })


@api_view(["GET"])
def my_bids_api(request):
    bids = (
        Bid.objects
        .filter(user=request.user)
        .select_related("project", "user")
        .prefetch_related("assignment")
        .order_by("-created_at")
    )
    return Response(BidSerializer(bids, many=True).data)


@api_view(["GET"])
def all_bids_api(request):
    """Industry/admin view: all bids with embedded assignment data."""
    if not _is_admin(request.user):
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    bids = (
        Bid.objects
        .select_related("project", "user")
        .prefetch_related("assignment__bid__project", "assignment__bid__user")
        .order_by("-created_at")
    )
    return Response(BidSerializer(bids, many=True).data)


@api_view(["POST"])
def bid_status_update_api(request, bid_id):
    """Industry/admin: shortlist, select, reject, etc. a bid."""
    if not _is_admin(request.user):
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    bid = get_object_or_404(Bid.objects.select_related("user", "project"), id=bid_id)
    serializer = BidStatusUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data

    new_status = d["status"]
    allowed = NEXT_ALLOWED_STATUSES.get(bid.status, [])
    if new_status not in allowed:
        return Response(
            {"detail": "Cannot transition bid from '{}' to '{}'.".format(bid.status, new_status)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        bid.status = new_status
        bid.save()

        # Create/update assignment when bid is selected
        if new_status == "selected":
            assignment, _ = Assignment.objects.get_or_create(
                bid=bid,
                defaults={
                    "timeline": d.get("timeline") or bid.project.default_timeline,
                    "project_details": d.get("project_details") or bid.project.description,
                    "expected_submission_date": d.get("expected_submission_date", ""),
                    "allocated_earning": d.get("allocated_earning") or bid.amount,
                    "status": "selected",
                },
            )
            if not _:  # already existed — update fields
                assignment.timeline = d.get("timeline") or assignment.timeline
                assignment.project_details = d.get("project_details") or assignment.project_details
                if d.get("expected_submission_date"):
                    assignment.expected_submission_date = d["expected_submission_date"]
                if d.get("allocated_earning"):
                    assignment.allocated_earning = d["allocated_earning"]
                assignment.status = "selected"
                assignment.save()

            # Credit pending earnings
            earning, _ = Earning.objects.get_or_create(user=bid.user)
            earning.pending += assignment.allocated_earning
            earning.save()

        elif new_status == "allocated":
            assignment = getattr(bid, "assignment", None)
            if assignment:
                assignment.status = "allocated"
                if d.get("allocated_earning"):
                    assignment.allocated_earning = d["allocated_earning"]
                assignment.save()

        elif new_status in ("in_progress", "submitted", "completed"):
            assignment = getattr(bid, "assignment", None)
            if assignment:
                assignment.status = new_status
                assignment.save()

        elif new_status == "rejected":
            assignment = getattr(bid, "assignment", None)
            if assignment:
                # Reverse any pending earnings
                earning, _ = Earning.objects.get_or_create(user=bid.user)
                if earning.pending >= assignment.allocated_earning:
                    earning.pending -= assignment.allocated_earning
                    earning.save()
                assignment.status = "rejected"
                assignment.save()

    event_labels = {
        "shortlisted": "Your bid has been shortlisted",
        "selected": "Your bid has been selected",
        "allocated": "Project has been allocated to you",
        "in_progress": "Your project is now in progress",
        "rejected": "Your bid was not selected",
        "completed": "Project marked as completed",
    }
    label = event_labels.get(new_status, "Bid status updated")
    _send_mail(
        bid.user,
        subject="{}: {}".format(label, bid.project.title),
        body="{} for project: {}.".format(label, bid.project.title),
        event="bid_status_{}".format(new_status),
    )

    return Response({"message": "Bid status updated to '{}'.".format(new_status), "bid": BidSerializer(bid).data})


# ---------------------------------------------------------------------------
# Assignments API
# ---------------------------------------------------------------------------

@api_view(["GET"])
def my_assignments_api(request):
    assignments = (
        Assignment.objects
        .filter(bid__user=request.user)
        .select_related("bid__project", "bid__user")
        .order_by("-allocated_at")
    )
    return Response(AssignmentSerializer(assignments, many=True).data)


@api_view(["POST"])
def submit_deliverable_api(request, assignment_id):
    assignment = get_object_or_404(
        Assignment.objects.select_related("bid__user", "bid__project"),
        id=assignment_id,
        bid__user=request.user,
    )

    if assignment.status not in ("allocated", "in_progress", "selected"):
        return Response({"detail": "Cannot submit deliverable for an assignment with status '{}'.".format(assignment.status)}, status=status.HTTP_400_BAD_REQUEST)

    serializer = DeliverableSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data

    file_content = _decode_base64_file(d["file_data"], d["file_name"])

    with transaction.atomic():
        assignment.submission_response = d["response"]
        assignment.submission_file_name = d["file_name"]
        assignment.submission_date = d.get("submission_date", "")
        assignment.submitted_at = timezone.now()
        assignment.status = "submitted"
        assignment.review_status = "pending"

        if file_content:
            assignment.submission_file.save(d["file_name"], file_content, save=False)

        assignment.save()

        assignment.bid.status = "submitted"
        assignment.bid.save()

    _send_mail(
        request.user,
        subject="Deliverable submitted: {}".format(assignment.bid.project.title),
        body="Your deliverable has been submitted and is pending review.",
        event="deliverable_submitted",
    )
    return Response({"message": "Deliverable submitted successfully.", "assignment": AssignmentSerializer(assignment).data})


@api_view(["POST"])
def review_assignment_api(request, assignment_id):
    if not _is_admin(request.user):
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    assignment = get_object_or_404(
        Assignment.objects.select_related("bid__user", "bid__project"),
        id=assignment_id,
    )

    if assignment.status != "submitted":
        return Response({"detail": "Can only review assignments with status 'submitted'."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ReviewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data

    with transaction.atomic():
        assignment.review_status = d["review_status"]
        assignment.review_comment = d.get("review_comment", "")
        assignment.reviewed_at = timezone.now()

        if d["review_status"] == "approved":
            assignment.status = "completed"
            assignment.bid.status = "completed"
            assignment.bid.save()

            # Release earnings
            earn_amount = d.get("earning_amount") or assignment.allocated_earning
            assignment.released_earning = earn_amount

            earning, _ = Earning.objects.get_or_create(user=assignment.bid.user)
            if earning.pending >= earn_amount:
                earning.pending -= earn_amount
            earning.total += earn_amount
            earning.save()

            TxnModel.objects.create(
                user=assignment.bid.user,
                amount=earn_amount,
                txn_type="credit",
                status="completed",
                description="Payment for project: {}".format(assignment.bid.project.title),
            )

            _send_mail(
                assignment.bid.user,
                subject="Payment released: {}".format(assignment.bid.project.title),
                body="Your deliverable has been approved. INR {:,.0f} has been credited to your account.".format(earn_amount),
                event="payment_released",
            )
        else:
            assignment.status = "in_progress"
            assignment.bid.status = "in_progress"
            assignment.bid.save()

            _send_mail(
                assignment.bid.user,
                subject="Revision requested: {}".format(assignment.bid.project.title),
                body="Reviewer comment: {}".format(d.get("review_comment", "")),
                event="revision_requested",
            )

        assignment.save()

    return Response({"message": "Assignment reviewed.", "assignment": AssignmentSerializer(assignment).data})


# ---------------------------------------------------------------------------
# Earnings / Transactions / Withdrawals API
# ---------------------------------------------------------------------------

@api_view(["GET"])
def earnings_api(request):
    earning, _ = Earning.objects.get_or_create(user=request.user)
    txns = TxnModel.objects.filter(user=request.user).order_by("-created_at")[:50]
    return Response({
        "summary": EarningsSerializer(earning).data,
        "transactions": TransactionSerializer(txns, many=True).data,
    })


@api_view(["POST"])
def create_withdraw_request_api(request):
    profile = request.user.profile
    if profile.status != "verified":
        return Response({"detail": "Your account must be verified to request a withdrawal."}, status=status.HTTP_403_FORBIDDEN)

    serializer = WithdrawSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data

    earning, _ = Earning.objects.get_or_create(user=request.user)
    available = earning.available_balance()
    amount = d["amount"]

    if amount <= 0:
        return Response({"detail": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)
    if amount > available:
        return Response({"detail": "Insufficient balance. Available: INR {:,.2f}".format(available)}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        wr = WithdrawRequest.objects.create(
            user=request.user,
            amount=amount,
            payment_method=d["payment_method"],
            payment_details=d["payment_details"],
            status="pending",
        )
        earning.pending += amount
        earning.save()
        TxnModel.objects.create(
            user=request.user,
            amount=amount,
            txn_type="withdrawal",
            status="pending",
            description="Withdrawal request #{}".format(wr.id),
        )

    _send_mail(
        request.user,
        subject="Withdrawal request submitted",
        body="Your withdrawal request of INR {:,.2f} has been submitted.".format(amount),
        event="withdrawal_requested",
    )
    return Response({"message": "Withdrawal request created.", "request": WithdrawRequestSerializer(wr).data})


@api_view(["GET"])
def my_withdraw_requests_api(request):
    items = WithdrawRequest.objects.filter(user=request.user).order_by("-created_at")
    return Response(WithdrawRequestSerializer(items, many=True).data)


# ---------------------------------------------------------------------------
# System Mails API
# ---------------------------------------------------------------------------

@api_view(["GET"])
def user_mails_api(request):
    mails = SystemMail.objects.filter(user=request.user)
    return Response(SystemMailSerializer(mails, many=True).data)


@api_view(["POST"])
def mark_mail_read_api(request, mail_id):
    mail = get_object_or_404(SystemMail, id=mail_id, user=request.user)
    mail.is_read = True
    mail.save(update_fields=["is_read"])
    return Response({"message": "Mail marked as read."})


@api_view(["POST"])
def mark_all_mails_read_api(request):
    SystemMail.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({"message": "All mails marked as read."})


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------

@api_view(["GET"])
def admin_pending_users_api(request):
    if not _is_admin(request.user):
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    users = User.objects.filter(
        profile__status="pending_verification"
    ).select_related("profile", "verification").prefetch_related()
    return Response(PendingUserSerializer(users, many=True).data)


@api_view(["POST"])
def admin_verify_user_api(request):
    """Accept/reject a researcher by email."""
    if not _is_admin(request.user):
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    email = request.data.get("email", "").lower()
    action = request.data.get("action", "")
    reason = request.data.get("reason", "")

    if not email:
        return Response({"detail": "email is required."}, status=status.HTTP_400_BAD_REQUEST)
    if action not in ("verified", "rejected"):
        return Response({"detail": "action must be 'verified' or 'rejected'."}, status=status.HTTP_400_BAD_REQUEST)

    target = get_object_or_404(User, email=email)
    profile = target.profile

    if action == "verified":
        profile.status = "verified"
        profile.rejection_reason = ""
        profile.save()
        _send_mail(
            target,
            subject="Verification Approved",
            body="Your Vidnex account has been verified. You can now bid on projects.",
            event="verification_approved",
        )
        return Response({"message": "User verified successfully."})
    else:
        profile.status = "rejected"
        profile.rejection_reason = reason or "Verification details did not meet requirements."
        profile.save()
        _send_mail(
            target,
            subject="Verification Rejected",
            body="Your verification was rejected. Reason: {}. Please update your details and resubmit.".format(reason),
            event="verification_rejected",
        )
        return Response({"message": "User rejected.", "reason": profile.rejection_reason})


@api_view(["POST"])
def admin_approve_user_api(request, user_id):
    """Legacy endpoint — approve by user ID."""
    if not _is_admin(request.user):
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    target = get_object_or_404(User, id=user_id)
    target.profile.status = "verified"
    target.profile.rejection_reason = ""
    target.profile.save()
    _send_mail(target, "Verification Approved", "Your account has been verified.", event="verification_approved")
    return Response({"message": "User approved."})


@api_view(["POST"])
def admin_reject_user_api(request, user_id):
    """Legacy endpoint — reject by user ID."""
    if not _is_admin(request.user):
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    reason = request.data.get("reason", "Verification details did not meet requirements.")
    target = get_object_or_404(User, id=user_id)
    target.profile.status = "rejected"
    target.profile.rejection_reason = reason
    target.profile.save()
    _send_mail(target, "Verification Rejected", "Reason: {}".format(reason), event="verification_rejected")
    return Response({"message": "User rejected.", "reason": reason})


@api_view(["GET"])
def admin_all_withdrawals_api(request):
    if not _is_admin(request.user):
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    items = WithdrawRequest.objects.select_related("user").order_by("-created_at")
    return Response(WithdrawRequestSerializer(items, many=True).data)


@api_view(["POST"])
def admin_process_withdrawal_api(request, withdraw_id):
    if not _is_admin(request.user):
        return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    wr = get_object_or_404(WithdrawRequest, id=withdraw_id)
    if wr.status != "pending":
        return Response({"detail": "Only pending requests can be processed."}, status=status.HTTP_400_BAD_REQUEST)

    action = request.data.get("action", "")
    if action not in ("completed", "rejected"):
        return Response({"detail": "action must be 'completed' or 'rejected'."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        earning, _ = Earning.objects.get_or_create(user=wr.user)
        # Reverse the pending hold
        if earning.pending >= wr.amount:
            earning.pending -= wr.amount

        if action == "completed":
            wr.status = "completed"
            wr.reviewed_by = request.user
            wr.reviewed_at = timezone.now()
            earning.withdrawn += wr.amount
            earning.save()
            TxnModel.objects.create(
                user=wr.user,
                amount=wr.amount,
                txn_type="withdrawal",
                status="completed",
                description="Withdrawal completed #{}".format(wr.id),
            )
            _send_mail(
                wr.user,
                subject="Withdrawal processed",
                body="Your withdrawal of INR {:,.2f} has been processed.".format(wr.amount),
                event="withdrawal_completed",
            )
        else:
            reason = request.data.get("reason", "")
            wr.status = "rejected"
            wr.rejection_reason = reason
            wr.reviewed_by = request.user
            wr.reviewed_at = timezone.now()
            earning.save()
            _send_mail(
                wr.user,
                subject="Withdrawal rejected",
                body="Your withdrawal request was rejected. Reason: {}".format(reason),
                event="withdrawal_rejected",
            )

        wr.save()

    return Response({"message": "Withdrawal {}".format(action), "request": WithdrawRequestSerializer(wr).data})

