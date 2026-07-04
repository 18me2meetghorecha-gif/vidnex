from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import Bid, Project, Transaction, VerificationDetail, WithdrawRequest


class ResearcherWorkflowTests(APITestCase):
	def setUp(self):
		self.client = APIClient()

	def _register_user(self, email="researcher1@gmail.com", full_name="Researcher One", password="securePass123"):
		return self.client.post(
			reverse("register-api"),
			{
				"full_name": full_name,
				"email": email,
				"password": password,
			},
			format="json",
		)

	def _login_user(self, email="researcher1@gmail.com", password="securePass123"):
		return self.client.post(
			reverse("login-api"),
			{
				"email": email,
				"password": password,
			},
			format="json",
		)

	def _verification_payload(self):
		pdf_content = b"%PDF-1.4 test pdf"
		return {
			"work_company": "ACME Labs",
			"work_role": "ML Engineer",
			"work_years": 4,
			"education_degree": "B.Tech",
			"education_university": "IIT Test",
			"education_year": 2021,
			"resume": SimpleUploadedFile("resume.pdf", pdf_content, content_type="application/pdf"),
			"certificates": SimpleUploadedFile("cert.pdf", pdf_content, content_type="application/pdf"),
			"id_proof": SimpleUploadedFile("id.pdf", pdf_content, content_type="application/pdf"),
		}

	def test_registration_requires_gmail(self):
		response = self.client.post(
			reverse("register-api"),
			{
				"full_name": "Not Gmail",
				"email": "demo@yahoo.com",
				"password": "securePass123",
			},
			format="json",
		)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_full_pending_to_verified_bidding_flow(self):
		register_resp = self._register_user()
		self.assertEqual(register_resp.status_code, status.HTTP_201_CREATED)
		self.assertEqual(register_resp.data["status"], "pending_verification")

		login_resp = self._login_user()
		self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
		self.assertEqual(login_resp.data["status"], "pending_verification")

		projects_resp = self.client.get(reverse("projects-api"))
		self.assertEqual(projects_resp.status_code, status.HTTP_200_OK)
		project_id = projects_resp.data[0]["id"]

		blocked_bid_resp = self.client.post(
			reverse("place-bid-api"),
			{"project_id": project_id, "amount": "55000.00", "proposal_note": "My proposal"},
			format="json",
		)
		self.assertEqual(blocked_bid_resp.status_code, status.HTTP_403_FORBIDDEN)
		self.assertIn("under verification", blocked_bid_resp.data["detail"])

		verify_resp = self.client.post(reverse("verification-submit-api"), self._verification_payload())
		self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)
		self.assertEqual(verify_resp.data["status"], "pending_verification")
		self.assertTrue(VerificationDetail.objects.filter(user__email="researcher1@gmail.com").exists())

		admin = User.objects.create_user(username="admin@gmail.com", email="admin@gmail.com", password="admin12345")
		admin.profile.full_name = "Admin"
		admin.profile.role = "admin"
		admin.profile.status = "verified"
		admin.profile.save()

		self.client.logout()
		self.client.post(reverse("login-api"), {"email": "admin@gmail.com", "password": "admin12345"}, format="json")

		pending_resp = self.client.get(reverse("admin-pending-users-api"))
		self.assertEqual(pending_resp.status_code, status.HTTP_200_OK)
		self.assertGreaterEqual(len(pending_resp.data), 1)

		target = User.objects.get(email="researcher1@gmail.com")
		approve_resp = self.client.post(reverse("admin-approve-user-api", kwargs={"user_id": target.id}), {}, format="json")
		self.assertEqual(approve_resp.status_code, status.HTTP_200_OK)

		target.refresh_from_db()
		self.assertEqual(target.profile.status, "verified")

		self.client.logout()
		self._login_user()

		allowed_bid_resp = self.client.post(
			reverse("place-bid-api"),
			{"project_id": project_id, "amount": "55000.00", "proposal_note": "My proposal"},
			format="json",
		)
		self.assertEqual(allowed_bid_resp.status_code, status.HTTP_200_OK)
		self.assertTrue(Bid.objects.filter(user=target, project_id=project_id).exists())

	def test_admin_reject_flow_and_reason(self):
		self._register_user(email="rejectme@gmail.com", full_name="Reject Me")
		self._login_user(email="rejectme@gmail.com")
		self.client.post(reverse("verification-submit-api"), self._verification_payload())
		self.client.logout()

		admin = User.objects.create_user(username="admin2@gmail.com", email="admin2@gmail.com", password="admin12345")
		admin.profile.full_name = "Admin Two"
		admin.profile.role = "admin"
		admin.profile.status = "verified"
		admin.profile.save()

		self.client.post(reverse("login-api"), {"email": "admin2@gmail.com", "password": "admin12345"}, format="json")
		target = User.objects.get(email="rejectme@gmail.com")

		reject_resp = self.client.post(
			reverse("admin-reject-user-api", kwargs={"user_id": target.id}),
			{"reason": "Documents unclear"},
			format="json",
		)
		self.assertEqual(reject_resp.status_code, status.HTTP_200_OK)

		target.refresh_from_db()
		self.assertEqual(target.profile.status, "rejected")
		self.assertEqual(target.profile.rejection_reason, "Documents unclear")

	def test_withdraw_request_validations(self):
		self._register_user(email="verified@gmail.com", full_name="Verified User")
		user = User.objects.get(email="verified@gmail.com")
		user.profile.status = "verified"
		user.profile.save()
		user.earning.total = 1000
		user.earning.pending = 0
		user.earning.withdrawn = 0
		user.earning.save()

		self._login_user(email="verified@gmail.com")

		invalid_resp = self.client.post(
			reverse("withdraw-request-api"),
			{
				"amount": "1500.00",
				"payment_method": "upi",
				"payment_details": "upi-id@okhdfcbank",
			},
			format="json",
		)
		self.assertEqual(invalid_resp.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn("Cannot withdraw", invalid_resp.data["detail"])

		valid_resp = self.client.post(
			reverse("withdraw-request-api"),
			{
				"amount": "600.00",
				"payment_method": "upi",
				"payment_details": "upi-id@okhdfcbank",
			},
			format="json",
		)
		self.assertEqual(valid_resp.status_code, status.HTTP_200_OK)
		self.assertTrue(WithdrawRequest.objects.filter(user=user, amount="600.00").exists())
		self.assertTrue(Transaction.objects.filter(user=user, txn_type="withdrawal").exists())

	def test_verification_requires_file_types(self):
		self._register_user(email="filecheck@gmail.com", full_name="File Check")
		self._login_user(email="filecheck@gmail.com")

		bad_payload = {
			"work_company": "ACME Labs",
			"work_role": "ML Engineer",
			"work_years": 4,
			"education_degree": "B.Tech",
			"education_university": "IIT Test",
			"education_year": 2021,
			"resume": SimpleUploadedFile("resume.txt", b"not allowed", content_type="text/plain"),
			"certificates": SimpleUploadedFile("cert.pdf", b"%PDF-1.4", content_type="application/pdf"),
			"id_proof": SimpleUploadedFile("id.pdf", b"%PDF-1.4", content_type="application/pdf"),
		}

		response = self.client.post(reverse("verification-submit-api"), bad_payload)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_admin_cannot_approve_without_verification_submission(self):
		self._register_user(email="novalidation@gmail.com", full_name="No Verification")

		admin = User.objects.create_user(username="admin3@gmail.com", email="admin3@gmail.com", password="admin12345")
		admin.profile.full_name = "Admin Three"
		admin.profile.role = "admin"
		admin.profile.status = "verified"
		admin.profile.save()

		self.client.post(reverse("login-api"), {"email": "admin3@gmail.com", "password": "admin12345"}, format="json")
		target = User.objects.get(email="novalidation@gmail.com")

		approve_resp = self.client.post(reverse("admin-approve-user-api", kwargs={"user_id": target.id}), {}, format="json")
		self.assertEqual(approve_resp.status_code, status.HTTP_400_BAD_REQUEST)

	def test_admin_cannot_submit_verification(self):
		admin = User.objects.create_user(username="admin4@gmail.com", email="admin4@gmail.com", password="admin12345")
		admin.profile.full_name = "Admin Four"
		admin.profile.role = "admin"
		admin.profile.status = "verified"
		admin.profile.save()

		self.client.post(reverse("login-api"), {"email": "admin4@gmail.com", "password": "admin12345"}, format="json")
		response = self.client.post(reverse("verification-submit-api"), self._verification_payload())
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
