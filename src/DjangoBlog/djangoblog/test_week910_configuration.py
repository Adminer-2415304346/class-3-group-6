# SZX（第9—10周）：验证统一配置的覆盖、隔离和非法输入边界，不触发外部服务。
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from djangoblog.maintenance_config import (
    DEFAULT_OPTIONS,
    get_maintenance_option,
    get_maintenance_options,
)


@override_settings(MAINTENANCE_OPTIONS={})
class MaintenanceConfigurationTests(SimpleTestCase):
    def test_agreed_defaults(self):
        self.assertEqual(get_maintenance_option("RESET_SEND_COOLDOWN_SECONDS"), 60)
        self.assertEqual(get_maintenance_option("COMMENT_MAX_LENGTH"), 2000)
        self.assertEqual(get_maintenance_option("UPLOAD_MAX_BYTES"), 5 * 1024 * 1024)
        self.assertEqual(get_maintenance_option("ROBOT_ALLOWED_ACTIONS"), ("python_version",))

    @override_settings(MAINTENANCE_OPTIONS={"OAUTH_STATE_TTL_SECONDS": 5})
    def test_partial_override_keeps_other_defaults(self):
        self.assertEqual(get_maintenance_option("OAUTH_STATE_TTL_SECONDS"), 5)
        self.assertEqual(get_maintenance_option("OAUTH_BIND_TTL_SECONDS"), 600)

    def test_returned_options_do_not_mutate_defaults(self):
        options = get_maintenance_options()
        options["RESET_MAX_FAILURES"] = 999
        self.assertEqual(get_maintenance_option("RESET_MAX_FAILURES"), 5)
        with self.assertRaises(TypeError):
            DEFAULT_OPTIONS["RESET_MAX_FAILURES"] = 999

    def test_unknown_requested_option_is_rejected(self):
        for name in ["RESET_TYPO", None, []]:
            with self.subTest(name=name), self.assertRaises(ImproperlyConfigured):
                get_maintenance_option(name)

    def test_non_dictionary_override_is_rejected(self):
        for value in [None, [], "settings"]:
            with self.subTest(value=value), override_settings(MAINTENANCE_OPTIONS=value):
                with self.assertRaises(ImproperlyConfigured):
                    get_maintenance_options()

    @override_settings(MAINTENANCE_OPTIONS={"RESET_TYPO": 1})
    def test_unknown_override_key_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            get_maintenance_options()

    def test_nonpositive_or_noninteger_limit_is_rejected(self):
        for value in [0, -1, True, False, 1.5, "60", None]:
            with self.subTest(value=value):
                with override_settings(MAINTENANCE_OPTIONS={"COMMENT_INTERVAL_SECONDS": value}):
                    with self.assertRaises(ImproperlyConfigured):
                        get_maintenance_options()

    @override_settings(MAINTENANCE_OPTIONS={"UPLOAD_ALLOWED_FORMATS": ["PNG"]})
    def test_supported_sequence_is_returned_as_immutable_tuple(self):
        self.assertEqual(get_maintenance_option("UPLOAD_ALLOWED_FORMATS"), ("PNG",))

    def test_invalid_upload_formats_are_rejected(self):
        for value in [[], "PNG", ["SVG"], ["PNG", "PNG"], [42]]:
            with self.subTest(value=value):
                with override_settings(MAINTENANCE_OPTIONS={"UPLOAD_ALLOWED_FORMATS": value}):
                    with self.assertRaises(ImproperlyConfigured):
                        get_maintenance_options()

    def test_action_registry_is_explicit_and_can_be_disabled(self):
        with override_settings(MAINTENANCE_OPTIONS={"ROBOT_ALLOWED_ACTIONS": []}):
            self.assertEqual(get_maintenance_option("ROBOT_ALLOWED_ACTIONS"), ())
        with override_settings(MAINTENANCE_OPTIONS={"ROBOT_ALLOWED_ACTIONS": ["arbitrary_shell"]}):
            with self.assertRaises(ImproperlyConfigured):
                get_maintenance_options()
