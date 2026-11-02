"""SZX（第9—10周）：浏览量与受控图片上传的请求、存储及回归验证。"""

import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from blog.models import Article, Category
from djangoblog.utils import get_sha256


def image_bytes(image_format="PNG", size=(12, 8)):
    with Image.new("RGB", size, "#427650") as image, io.BytesIO() as output:
        image.save(output, format=image_format)
        return output.getvalue()


class AtomicArticleViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user(username="week910-author")
        cls.category = Category.objects.create(name="Week910 counter")
        cls.article = Article.objects.create(
            title="Counter example", body="Published body", author=cls.author,
            category=cls.category, status="p", views=10,
        )

    def setUp(self):
        cache.clear()

    def test_two_stale_instances_both_increment_the_database(self):
        first = Article.objects.get(pk=self.article.pk)
        second = Article.objects.get(pk=self.article.pk)
        first.viewed()
        second.viewed()
        self.assertEqual(Article.objects.get(pk=self.article.pk).views, 12)
        self.assertEqual(second.views, 12)

    def test_instance_keeps_a_plain_integer(self):
        self.article.viewed()
        self.assertIs(type(self.article.views), int)
        self.assertEqual(self.article.views, 11)

    def test_later_save_does_not_reapply_the_increment(self):
        self.article.viewed()
        self.article.title = "Updated title"
        self.article.save()
        self.article.refresh_from_db()
        self.assertEqual(self.article.views, 11)
        self.assertEqual(self.article.title, "Updated title")

    def test_counter_refresh_preserves_unsaved_content(self):
        self.article.body = "Unsaved local body"
        self.article.viewed()
        self.assertEqual(self.article.body, "Unsaved local body")
        self.assertEqual(Article.objects.get(pk=self.article.pk).body, "Published body")

    def test_deleted_row_is_not_silently_recreated(self):
        stale = Article.objects.get(pk=self.article.pk)
        Article.objects.filter(pk=stale.pk).delete()
        with self.assertRaises(Article.DoesNotExist):
            stale.viewed()
        self.assertFalse(Article.objects.filter(pk=stale.pk).exists())

    def test_unsaved_instance_cannot_increment_an_existing_id(self):
        unsaved = Article(pk=self.article.pk)
        with self.assertRaises(ValueError):
            unsaved.viewed()
        self.assertEqual(Article.objects.get(pk=self.article.pk).views, 10)

    def test_http_detail_updates_database_and_render_context_once(self):
        for expected in [11, 12]:
            response = self.client.get(self.article.get_absolute_url())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["article"].views, expected)
            self.assertEqual(Article.objects.get(pk=self.article.pk).views, expected)


class ImageUploadFunctionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.staff = users.create_user(username="week910-staff", is_staff=True)
        cls.reader = users.create_user(username="week910-reader")
        cls.inactive = users.create_user(
            username="week910-inactive", is_staff=True, is_active=False,
        )

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="week910-upload-tests-")
        self.addCleanup(self.directory.cleanup)
        self.media = Path(self.directory.name) / "media"
        options = override_settings(
            MEDIA_ROOT=str(self.media), MEDIA_URL="/media/",
            STATICFILES=str(Path(self.directory.name) / "legacy"),
            SECRET_KEY="week910-functional-test-key-only", MAINTENANCE_OPTIONS={},
        )
        options.enable()
        self.addCleanup(options.disable)
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.staff)
        request = RequestFactory().get("/")
        self.token = get_token(request)
        self.csrf_secret = request.META["CSRF_COOKIE"]
        self.client.cookies[settings.CSRF_COOKIE_NAME] = self.csrf_secret
        self.url = reverse("blog:upload")

    def uploaded(self, data=None, name="sample.png", content_type="image/png"):
        return SimpleUploadedFile(
            name, image_bytes() if data is None else data, content_type=content_type,
        )

    def post(self, uploaded=None, **kwargs):
        return self.client.post(
            self.url, {"file": uploaded if uploaded is not None else self.uploaded()},
            HTTP_X_CSRFTOKEN=self.token, **kwargs,
        )

    def files(self):
        return [path for path in Path(self.directory.name).rglob("*") if path.is_file()]

    def assert_invalid(self, response, code="invalid_file"):
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["code"], code)
        self.assertEqual(self.files(), [])

    def test_anonymous_user_is_forbidden_even_with_legacy_sign(self):
        self.client.logout()
        self.client.cookies[settings.CSRF_COOKIE_NAME] = self.csrf_secret
        sign = get_sha256(get_sha256(settings.SECRET_KEY))
        response = self.client.post(
            self.url + "?sign=" + sign, {"file": self.uploaded()},
            HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.files(), [])

    def test_regular_user_is_forbidden(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.files(), [])

    def test_inactive_staff_is_forbidden(self):
        self.client.force_login(self.inactive)
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.files(), [])

    def test_staff_without_csrf_is_forbidden(self):
        self.client.cookies.pop(settings.CSRF_COOKIE_NAME)
        response = self.client.post(self.url, {"file": self.uploaded()})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.files(), [])

    def test_non_post_methods_are_rejected(self):
        for method in ["GET", "PUT", "DELETE", "HEAD", "OPTIONS"]:
            with self.subTest(method=method):
                response = self.client.generic(method, self.url, HTTP_X_CSRFTOKEN=self.token)
                self.assertEqual(response.status_code, 405)
        self.assertEqual(self.files(), [])

    def test_actual_png_jpeg_and_webp_are_saved_with_matching_formats(self):
        for image_format, extension in [("PNG", ".png"), ("JPEG", ".jpg"), ("WEBP", ".webp")]:
            with self.subTest(image_format=image_format):
                response = self.post(self.uploaded(image_bytes(image_format)))
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["code"], "uploaded")
                self.assertTrue(payload["success"])
                self.assertEqual(payload["data"]["format"], image_format)
                self.assertTrue(payload["data"]["name"].endswith(extension))
                self.assertTrue(payload["data"]["url"].startswith("/media/images/"))
                with default_storage.open(payload["data"]["name"], "rb") as stored:
                    with Image.open(stored) as image:
                        self.assertEqual(image.format, image_format)
                        self.assertEqual(image.size, (12, 8))
                self.assertGreater(payload["data"]["size"], 0)

    def test_missing_file_field_is_rejected(self):
        response = self.client.post(self.url, {}, HTTP_X_CSRFTOKEN=self.token)
        self.assert_invalid(response)

    def test_wrong_field_name_is_rejected(self):
        response = self.client.post(
            self.url, {"sample.png": self.uploaded()}, HTTP_X_CSRFTOKEN=self.token,
        )
        self.assert_invalid(response)

    def test_multiple_files_are_rejected_before_saving(self):
        response = self.client.post(
            self.url, {"file": [self.uploaded(), self.uploaded()]},
            HTTP_X_CSRFTOKEN=self.token,
        )
        self.assert_invalid(response)

    def test_additional_file_field_is_rejected(self):
        response = self.client.post(
            self.url, {"file": self.uploaded(), "other": self.uploaded()},
            HTTP_X_CSRFTOKEN=self.token,
        )
        self.assert_invalid(response)

    def test_empty_file_is_rejected(self):
        self.assert_invalid(self.post(self.uploaded(b"")))

    def test_script_renamed_to_png_is_rejected(self):
        self.assert_invalid(self.post(self.uploaded(b"<script>alert(1)</script>")))

    def test_truncated_image_is_rejected(self):
        self.assert_invalid(self.post(self.uploaded(image_bytes()[:-9])))

    def test_disallowed_decodable_format_is_rejected(self):
        self.assert_invalid(self.post(self.uploaded(image_bytes("BMP"))))

    def test_client_extension_and_mime_do_not_choose_storage_format(self):
        response = self.post(self.uploaded(name="../../payload.html", content_type="text/html"))
        self.assertEqual(response.status_code, 200)
        name = response.json()["data"]["name"]
        self.assertTrue(name.endswith(".png"))
        self.assertNotIn("payload", name)
        self.assertNotIn("..", name)
        self.assertTrue((self.media / name).resolve().is_relative_to(self.media.resolve()))

    def test_same_client_filename_does_not_overwrite_existing_file(self):
        first = self.post().json()["data"]["name"]
        first_data = default_storage.open(first, "rb").read()
        second = self.post().json()["data"]["name"]
        self.assertNotEqual(first, second)
        with default_storage.open(first, "rb") as stored:
            self.assertEqual(stored.read(), first_data)
        self.assertEqual(len(self.files()), 2)

    @override_settings(MAINTENANCE_OPTIONS={"UPLOAD_MAX_BYTES": 32})
    def test_oversize_input_is_rejected_before_decode(self):
        self.assert_invalid(self.post(), "file_too_large")

    def test_exact_byte_limit_is_accepted(self):
        data = image_bytes()
        with override_settings(MAINTENANCE_OPTIONS={"UPLOAD_MAX_BYTES": len(data)}):
            self.assertEqual(self.post(self.uploaded(data)).status_code, 200)

    @override_settings(MAINTENANCE_OPTIONS={"UPLOAD_MAX_PIXELS": 95})
    def test_pixel_limit_is_checked(self):
        self.assert_invalid(self.post())

    @override_settings(MAINTENANCE_OPTIONS={"UPLOAD_ALLOWED_FORMATS": ["JPEG"]})
    def test_configuration_controls_actual_format_allowlist(self):
        self.assert_invalid(self.post())

    def test_trailing_payload_is_not_stored(self):
        response = self.post(self.uploaded(image_bytes() + b"<script>untrusted</script>"))
        self.assertEqual(response.status_code, 200)
        with default_storage.open(response.json()["data"]["name"], "rb") as stored:
            self.assertNotIn(b"<script>", stored.read())

    def test_camera_orientation_is_applied_before_metadata_removal(self):
        with Image.new("RGB", (12, 8), "green") as image, io.BytesIO() as output:
            exif = Image.Exif()
            exif[274] = 6
            image.save(output, format="JPEG", exif=exif)
            response = self.post(self.uploaded(output.getvalue(), name="camera.jpg"))
        self.assertEqual(response.status_code, 200)
        with default_storage.open(response.json()["data"]["name"], "rb") as stored:
            with Image.open(stored) as image:
                self.assertEqual(image.size, (8, 12))
                self.assertEqual(len(image.getexif()), 0)

    def test_storage_failure_returns_recoverable_error(self):
        with patch("django.core.files.storage.default_storage.save", side_effect=OSError("disk")):
            response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "storage_unavailable")
        self.assertEqual(self.files(), [])

    def test_staff_can_open_upload_page_with_csrf_token(self):
        response = self.client.get(reverse("blog:upload_page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'name="file"')
        self.assertContains(response, self.url)

    def test_upload_page_requires_staff(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse("blog:upload_page")).status_code, 403)
        self.client.logout()
        response = self.client.get(reverse("blog:upload_page"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])
