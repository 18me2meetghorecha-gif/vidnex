from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


VERIFICATION_STATUS_CHOICES = (
	("pending_verification", "Pending Verification"),
	("verified", "Verified"),
	("rejected", "Rejected"),
)

BID_STATUS_CHOICES = (
	("pending", "Pending"),
	("shortlisted", "Shortlisted"),
	("selected", "Selected"),
	("allocated", "Allocated"),
	("in_progress", "In Progress"),
	("submitted", "Submitted"),
	("completed", "Completed"),
	("rejected", "Rejected"),
)

WITHDRAW_STATUS_CHOICES = (
	("pending", "Pending"),
	("completed", "Completed"),
	("rejected", "Rejected"),
)

NEXT_ALLOWED_STATUSES = {
	"pending": ["shortlisted", "selected", "rejected"],
	"shortlisted": ["selected", "rejected"],
	"selected": ["allocated"],
	"allocated": ["in_progress", "submitted"],
	"in_progress": ["submitted"],
	"submitted": ["completed"],
	"rejected": [],
	"completed": [],
}


class UserProfile(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
	full_name = models.CharField(max_length=120)
	role = models.CharField(max_length=20, default="user")
	bio = models.TextField(blank=True)
	phone = models.CharField(max_length=50, blank=True)
	status = models.CharField(max_length=30, choices=VERIFICATION_STATUS_CHOICES, default="pending_verification")
	rejection_reason = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return "{} ({})".format(self.full_name, self.status)


class VerificationDetail(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="verification")

	work_company = models.CharField(max_length=120)
	work_role = models.CharField(max_length=120)
	work_years = models.PositiveIntegerField()

	education_degree = models.CharField(max_length=120)
	education_university = models.CharField(max_length=180)
	education_year = models.PositiveIntegerField()

	resume = models.FileField(upload_to="verification/resume/", blank=True)
	certificates = models.FileField(upload_to="verification/certificates/", blank=True)
	id_proof = models.FileField(upload_to="verification/id_proof/", blank=True)

	submitted_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return "Verification for {}".format(self.user.email)


class Project(models.Model):
	title = models.CharField(max_length=150)
	category = models.CharField(max_length=80, blank=True)
	description = models.TextField()
	min_budget = models.DecimalField(max_digits=12, decimal_places=2)
	max_budget = models.DecimalField(max_digits=12, decimal_places=2)
	default_timeline = models.CharField(max_length=80, default="8 weeks")
	active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.title


class Bid(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bids")
	project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="bids")
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	proposal_note = models.TextField(blank=True)
	status = models.CharField(max_length=20, choices=BID_STATUS_CHOICES, default="pending")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ("user", "project")

	def __str__(self):
		return "{} bid on {}".format(self.user.email, self.project.title)


class Assignment(models.Model):
	bid = models.OneToOneField(Bid, on_delete=models.CASCADE, related_name="assignment")
	timeline = models.CharField(max_length=120, default="8 weeks")
	project_details = models.TextField(blank=True)
	expected_submission_date = models.CharField(max_length=32, blank=True)
	allocated_earning = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	released_earning = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	submission_response = models.TextField(blank=True)
	submission_file_name = models.CharField(max_length=200, blank=True)
	submission_file = models.FileField(upload_to="submissions/", null=True, blank=True)
	submission_date = models.CharField(max_length=32, blank=True)
	submitted_at = models.DateTimeField(null=True, blank=True)
	review_status = models.CharField(max_length=30, blank=True, default="pending")
	review_comment = models.TextField(blank=True)
	reviewed_at = models.DateTimeField(null=True, blank=True)
	status = models.CharField(max_length=20, default="allocated")
	allocated_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return "Assignment for bid #{}".format(self.bid_id)


class Earning(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="earning")
	total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	pending = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	updated_at = models.DateTimeField(auto_now=True)

	def available_balance(self):
		value = self.total - self.pending - self.withdrawn
		return value if value > 0 else Decimal("0.00")

	def __str__(self):
		return "Earnings for {}".format(self.user.email)


class Transaction(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	txn_type = models.CharField(max_length=20)
	status = models.CharField(max_length=20, default="completed")
	description = models.CharField(max_length=255, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return "{} {}".format(self.txn_type, self.amount)


class WithdrawRequest(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="withdraw_requests")
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	payment_method = models.CharField(max_length=20)
	payment_details = models.TextField()
	status = models.CharField(max_length=20, choices=WITHDRAW_STATUS_CHOICES, default="pending")
	rejection_reason = models.TextField(blank=True)
	reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_withdrawals")
	reviewed_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return "Withdraw {} by {}".format(self.amount, self.user.email)


class SystemMail(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="system_mails")
	subject = models.CharField(max_length=150)
	body = models.TextField()
	is_read = models.BooleanField(default=False)
	event = models.CharField(max_length=50, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return "{} → {}".format(self.subject, self.user.email)


@receiver(post_save, sender=User)
def create_user_related_records(sender, instance, created, **kwargs):
	if created:
		UserProfile.objects.get_or_create(user=instance, defaults={"full_name": instance.get_full_name() or instance.username})
		Earning.objects.get_or_create(user=instance)
