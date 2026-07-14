import base64

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from rest_framework import serializers

from .models import (
    Assignment,
    Bid,
    Earning,
    Project,
    SystemMail,
    Transaction,
    UserProfile,
    VerificationDetail,
    WithdrawRequest,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(min_length=2, max_length=120)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, write_only=True)
    password_confirm = serializers.CharField(min_length=6, write_only=True)
    role = serializers.ChoiceField(choices=["researcher", "industry"], default="researcher")

    def validate_email(self, value):
        lowered = value.lower()
        if not lowered.endswith("@gmail.com"):
            raise serializers.ValidationError("Only Gmail addresses are allowed.")
        if User.objects.filter(email=lowered).exists():
            raise serializers.ValidationError("Email already registered.")
        return lowered

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UpdateProfileSerializer(serializers.Serializer):
    bio = serializers.CharField(max_length=500, allow_blank=True, required=False)
    phone = serializers.CharField(max_length=50, allow_blank=True, required=False)


# ---------------------------------------------------------------------------
# Me / profile
# ---------------------------------------------------------------------------

class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    role = serializers.CharField()
    status = serializers.CharField()
    rejection_reason = serializers.CharField(allow_blank=True)
    bio = serializers.CharField(allow_blank=True)
    phone = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    researcher_details = serializers.DictField(allow_null=True)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

class VerificationDetailSerializer(serializers.ModelSerializer):
    resume_url = serializers.SerializerMethodField()
    certificates_url = serializers.SerializerMethodField()
    id_proof_url = serializers.SerializerMethodField()

    class Meta:
        model = VerificationDetail
        fields = [
            "work_company", "work_role", "work_years",
            "education_degree", "education_university", "education_year",
            "resume_url", "certificates_url", "id_proof_url",
            "submitted_at", "updated_at",
        ]

    def get_resume_url(self, obj):
        return obj.resume.url if obj.resume else None

    def get_certificates_url(self, obj):
        return obj.certificates.url if obj.certificates else None

    def get_id_proof_url(self, obj):
        return obj.id_proof.url if obj.id_proof else None


class VerificationSubmitSerializer(serializers.Serializer):
    """Accepts base64-encoded file data sent by the frontend."""
    work_company = serializers.CharField(max_length=140)
    work_role = serializers.CharField(max_length=140)
    work_years = serializers.IntegerField(min_value=0, max_value=60)
    education_degree = serializers.CharField(max_length=140)
    education_university = serializers.CharField(max_length=180)
    education_year = serializers.IntegerField(min_value=1950, max_value=2100)
    resume_name = serializers.CharField(max_length=180)
    resume_data = serializers.CharField()
    certificate_name = serializers.CharField(max_length=180, required=False, allow_blank=True, default="none")
    certificate_data = serializers.CharField(required=False, allow_blank=True, default="")
    id_proof_name = serializers.CharField(max_length=180)
    id_proof_data = serializers.CharField()

    def _decode_file(self, data_url, name):
        try:
            if "," in data_url:
                _, encoded = data_url.split(",", 1)
            else:
                encoded = data_url
            return ContentFile(base64.b64decode(encoded), name=name)
        except Exception:
            raise serializers.ValidationError("Invalid file data for {}.".format(name))


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class ProjectSerializer(serializers.ModelSerializer):
    budget = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "title", "category", "description",
            "min_budget", "max_budget", "budget",
            "default_timeline", "active", "created_at", "documents",
        ]

    def get_budget(self, obj):
        return "INR {:,.0f} - INR {:,.0f}".format(obj.min_budget, obj.max_budget)

    def get_documents(self, obj):
        return []


# ---------------------------------------------------------------------------
# Bids & Assignments
# ---------------------------------------------------------------------------

class BidCreateSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    proposal_note = serializers.CharField(allow_blank=True, required=False, default="")


class BidStatusUpdateSerializer(serializers.Serializer):
    status = serializers.CharField()
    timeline = serializers.CharField(required=False, allow_blank=True, default="")
    expected_submission_date = serializers.CharField(required=False, allow_blank=True, default="")
    project_details = serializers.CharField(required=False, allow_blank=True, default="")
    allocated_earning = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)


class AssignmentSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(source="bid.project_id")
    project_title = serializers.CharField(source="bid.project.title")
    researcher_email = serializers.EmailField(source="bid.user.email")
    bid_id = serializers.IntegerField(source="bid_id")

    class Meta:
        model = Assignment
        fields = [
            "id", "bid_id", "project_id", "project_title", "researcher_email",
            "timeline", "project_details", "expected_submission_date",
            "allocated_earning", "released_earning",
            "submission_response", "submission_file_name", "submission_date", "submitted_at",
            "review_status", "review_comment", "reviewed_at",
            "status", "allocated_at", "updated_at",
        ]


class BidSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source="project.title", read_only=True)
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    researcher_email = serializers.EmailField(source="user.email", read_only=True)
    assignment = AssignmentSerializer(read_only=True)

    class Meta:
        model = Bid
        fields = [
            "id", "project_id", "project_title", "researcher_email",
            "amount", "proposal_note", "status",
            "created_at", "updated_at", "assignment",
        ]


class DeliverableSubmitSerializer(serializers.Serializer):
    response = serializers.CharField(min_length=1)
    submission_date = serializers.CharField(required=False, allow_blank=True, default="")
    file_name = serializers.CharField(max_length=180)
    file_data = serializers.CharField()


class ReviewSerializer(serializers.Serializer):
    review_status = serializers.ChoiceField(choices=["approved", "changes_requested"])
    review_comment = serializers.CharField(allow_blank=True, required=False, default="")
    earning_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)


# ---------------------------------------------------------------------------
# Earnings / Transactions / Withdrawals
# ---------------------------------------------------------------------------

class EarningsSerializer(serializers.ModelSerializer):
    available = serializers.SerializerMethodField()

    class Meta:
        model = Earning
        fields = ["total", "pending", "withdrawn", "available", "updated_at"]

    def get_available(self, obj):
        return obj.available_balance()


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "amount", "txn_type", "status", "description", "created_at"]


class WithdrawSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=["upi", "bank"])
    payment_details = serializers.CharField()


class WithdrawRequestSerializer(serializers.ModelSerializer):
    researcher_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = WithdrawRequest
        fields = [
            "id", "researcher_email", "amount", "payment_method", "payment_details",
            "status", "rejection_reason", "created_at", "reviewed_at",
        ]


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class PendingUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="profile.full_name")
    status = serializers.CharField(source="profile.status")
    rejection_reason = serializers.CharField(source="profile.rejection_reason")
    verification_details = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "status", "rejection_reason", "date_joined", "verification_details"]

    def get_verification_details(self, obj):
        v = getattr(obj, "verification", None)
        if not v:
            return None
        def _url(f):
            try:
                return f.url if f else None
            except Exception:
                return None
        return {
            "work": {"company": v.work_company, "role": v.work_role, "years": v.work_years},
            "education": {"degree": v.education_degree, "university": v.education_university, "year": v.education_year},
            "documents": {
                "resume": {"name": v.resume.name.split("/")[-1] if v.resume else "", "url": _url(v.resume)},
                "certificates": {"name": v.certificates.name.split("/")[-1] if v.certificates else "", "url": _url(v.certificates)},
                "id_proof": {"name": v.id_proof.name.split("/")[-1] if v.id_proof else "", "url": _url(v.id_proof)},
            },
            "submitted_at": v.submitted_at.isoformat() if v.submitted_at else None,
        }


# ---------------------------------------------------------------------------
# System Mails
# ---------------------------------------------------------------------------

class SystemMailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemMail
        fields = ["id", "subject", "body", "is_read", "event", "created_at"]
