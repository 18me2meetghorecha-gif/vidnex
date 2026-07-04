from django.contrib import admin

from .models import Bid, Earning, Project, Transaction, UserProfile, VerificationDetail, WithdrawRequest


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ("full_name", "user", "role", "status", "created_at")
	list_filter = ("role", "status")
	search_fields = ("full_name", "user__email")


@admin.register(VerificationDetail)
class VerificationDetailAdmin(admin.ModelAdmin):
	list_display = ("user", "work_company", "work_role", "submitted_at")
	search_fields = ("user__email", "work_company", "education_university")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
	list_display = ("title", "min_budget", "max_budget", "active", "created_at")
	list_filter = ("active",)


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
	list_display = ("user", "project", "amount", "status", "created_at")
	list_filter = ("status",)


@admin.register(Earning)
class EarningAdmin(admin.ModelAdmin):
	list_display = ("user", "total", "pending", "withdrawn", "updated_at")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
	list_display = ("user", "txn_type", "amount", "status", "created_at")
	list_filter = ("txn_type", "status")


@admin.register(WithdrawRequest)
class WithdrawRequestAdmin(admin.ModelAdmin):
	list_display = ("user", "amount", "payment_method", "status", "created_at")
	list_filter = ("status", "payment_method")

# Register your models here.
