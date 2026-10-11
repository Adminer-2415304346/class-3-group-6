"""SZX：注册与找回密码的模板回归检查，不访问真实数据库或发送邮件。"""

from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from accounts.forms import ForgetPasswordForm, RegisterForm
from accounts.test_login_page import PageElements


@override_settings(COMPRESS_ENABLED=False)
class AccountLauncherPageTests(SimpleTestCase):
    pages = (
        ('account/registration_form.html', RegisterForm, 'register-form', '/register/'),
        ('account/forget_password.html', ForgetPasswordForm, 'reset-password-form', '/forget_password/'),
    )

    def render_page(self, template, form):
        return render_to_string(template, {
            'form': form,
            'csrf_token': 'test-csrf-token',
            'SITE_NAME': 'AI Agent 工程实践',
        })

    def test_forms_keep_native_post_csrf_field_names_order_and_required_flags(self):
        for template, form_type, form_id, action in self.pages:
            with self.subTest(template=template):
                form = form_type()
                page = PageElements(self.render_page(template, form))
                form_attrs = page.find('form', id=form_id)
                self.assertEqual(form_attrs['method'], 'post')
                self.assertEqual(form_attrs['action'], action)
                self.assertEqual(form_attrs['hx-boost'], 'false')
                self.assertEqual(page.find('input', name='csrfmiddlewaretoken')['value'], 'test-csrf-token')
                names = [attrs['name'] for tag, attrs in page.elements
                         if tag == 'input' and attrs.get('name') in form.fields]
                self.assertEqual(names, list(form.fields))
                for name, field in form.fields.items():
                    self.assertEqual('required' in page.find('input', name=name), field.required)
                self.assertNotIn('disabled', page.find('button', type='submit'))

    def test_passwords_are_native_masked_without_javascript_and_never_prefilled(self):
        for template, form_type, _, _ in self.pages:
            with self.subTest(template=template):
                page = PageElements(self.render_page(template, form_type()))
                password_inputs = [attrs for tag, attrs in page.elements
                                   if tag == 'input' and 'password' in attrs.get('name', '')]
                self.assertEqual(len(password_inputs), 2)
                for attrs in password_inputs:
                    self.assertEqual(attrs['type'], 'password')
                    self.assertEqual(attrs['autocomplete'], 'new-password')
                    self.assertNotIn('value', attrs)

    def test_register_errors_preserve_safe_nonsecret_fields_and_help_associations(self):
        secret = 'NeverRenderThisPassword_123!'
        with patch('accounts.forms.RegisterForm._post_clean'), \
                patch('accounts.forms.BlogUser.objects.filter') as users:
            users.return_value.exists.return_value = False
            form = RegisterForm(data={
                'username': '<kept-reader>', 'email': 'reader@example.org',
                'password1': secret, 'password2': '',
            })
            self.assertFalse(form.is_valid())
            # 模型校验已隔离；补入字段错误来覆盖模板的错误/帮助信息关联。
            form.add_error('username', '用户名包含不允许的字符。')
        html = self.render_page('account/registration_form.html', form)
        page = PageElements(html)
        self.assertEqual(page.find('input', name='username')['value'], '<kept-reader>')
        self.assertEqual(page.find('input', name='email')['value'], 'reader@example.org')
        self.assertNotIn('<kept-reader>', html)
        self.assertNotIn(secret, html)
        self.assertIn('aria-invalid="true"', html)
        username = page.find('input', name='username')
        self.assertIn('id_username-help', username['aria-describedby'].split())
        self.assertEqual(page.find('p', id='id_username-error')['role'], 'alert')
        self.assertIn('密码要求', html)

    def test_reset_errors_keep_email_and_code_without_passwords(self):
        secret = 'NeverRenderThisPassword_123!'
        with patch.object(ForgetPasswordForm, 'clean_email', return_value='reader@example.org'), \
                patch('accounts.forms.utils.verify', return_value='验证码错误'):
            form = ForgetPasswordForm(data={
                'new_password1': secret, 'new_password2': secret,
                'email': 'reader@example.org', 'code': '000000',
            })
            self.assertFalse(form.is_valid())
        html = self.render_page('account/forget_password.html', form)
        page = PageElements(html)
        self.assertNotIn(secret, html)
        self.assertEqual(page.find('input', name='email')['value'], 'reader@example.org')
        code = page.find('input', name='code')
        self.assertEqual(code['value'], '000000')
        self.assertEqual(code['aria-invalid'], 'true')
        self.assertEqual(page.find('p', id=code['aria-describedby'])['role'], 'alert')

    def test_code_button_uses_the_existing_endpoint_and_real_async_feedback(self):
        html = self.render_page('account/forget_password.html', ForgetPasswordForm())
        page = PageElements(html)
        form = page.find('form', id='reset-password-form')
        self.assertEqual(form['data-code-url'], '/forget_password_code/')
        button = page.find('button', id='btn')
        self.assertEqual(button['type'], 'button')
        self.assertEqual(button['@click'], 'sendCode()')
        self.assertEqual(button[':disabled'], 'codeSending || codeRemaining > 0')
        self.assertEqual(page.find('input', name='email')['type'], 'email')
        self.assertEqual(page.find('input', name='code')['autocomplete'], 'one-time-code')
        self.assertIn('role="status"', html)
        self.assertNotIn('codeSent = true', html)

    def test_account_links_use_full_navigation_not_body_swaps(self):
        for template, form_type, _, _ in self.pages:
            with self.subTest(template=template):
                html = self.render_page(template, form_type())
                page = PageElements(html)
                self.assertEqual(page.find('a', href='/login/')['hx-boost'], 'false')
                self.assertNotIn('hx-swap="outerHTML"', html)
                self.assertIn('favicon.svg?v=relay-1#site-brand-mark', html)

    def test_account_pages_have_distinct_layouts_and_labelled_wide_actions(self):
        for template, form_type, _, _ in self.pages:
            with self.subTest(template=template):
                html = self.render_page(template, form_type())
                page = PageElements(html)
                layout = 'launcher-register-page' if form_type is RegisterForm else 'launcher-reset-page'
                self.assertIn(layout, page.find('body')['class'].split())
                self.assertIn('launcher-fields-grid', html)
                self.assertIn('launcher-submit-wide', page.find('button', type='submit')['class'].split())
                back = page.find('a', **{'class': 'launcher-back'})
                self.assertEqual(back['href'], '/login/')
                self.assertEqual(back['hx-boost'], 'false')

    def test_transition_bootstrap_is_early_and_seam_is_decorative(self):
        for template, form_type, _, _ in self.pages:
            with self.subTest(template=template):
                html = self.render_page(template, form_type())
                page = PageElements(html)
                script = next(attrs for tag, attrs in page.elements
                              if tag == 'script' and 'accountTransitions.js' in attrs.get('src', ''))
                self.assertNotIn('async', script)
                self.assertNotIn('defer', script)
                self.assertNotIn('type', script)
                self.assertLess(html.index('accountTransitions.js'), html.index('</head>'))
                self.assertIn('@view-transition { navigation: auto; }', html)
                self.assertLess(html.index('@view-transition'), html.index('accountTransitions.js'))
                self.assertEqual(page.find('div', **{'class': 'account-entry-seam'})['aria-hidden'], 'true')
                self.assertNotIn('account-screen-curtain', html)

    def test_register_has_one_board_with_grouped_fields_and_accessible_flow_control(self):
        html = self.render_page('account/registration_form.html', RegisterForm())
        page = PageElements(html)
        self.assertIn('registration-board', html)
        fieldsets = [attrs for tag, attrs in page.elements if tag == 'fieldset']
        self.assertEqual(len(fieldsets), 2)
        self.assertEqual(page.find('main', id='main')['x-data'], 'accountFlow')
        self.assertEqual(page.find('section', **{'class': 'launcher-panel registration-board'})['x-data'], 'launcherAccount')
        self.assertIn('@click="toggleFlow()"', html)
        self.assertEqual(page.find('div', id='account-content')['tabindex'], '-1')
