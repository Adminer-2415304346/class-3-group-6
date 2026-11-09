from accounts.models import BlogUser
from blog.models import Article, Category
from django.test import Client, RequestFactory, TransactionTestCase
from django.urls import reverse
from djangoblog.utils import get_max_articleid_commentid

from comments.models import Comment, CommentPostState
from comments.templatetags.comments_tags import *

# Create your tests here.

class CommentsTest(TransactionTestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        from blog.models import BlogSettings
        value = BlogSettings()
        value.comment_need_review = True
        value.save()

        self.user = BlogUser.objects.create_superuser(
            email="liangliangyy1@gmail.com",
            username="liangliangyy1",
            password="liangliangyy1")

    def update_article_comment_status(self, article):
        comments = article.comment_set.all()
        for comment in comments:
            comment.is_enable = True
            comment.save()

    def expire_post_state(self):
        # WZY（第9—10周 C92）：同一用户的连续评论受 30 秒间隔与 120 秒重复窗口约束。
        # 本用例验证的是“审核开关 + 评论树”的既有逻辑，因此在两次提交之间清空发布状态，
        # 等价于时间窗已过期；限频/重复语义由 comments/test_week910_functional.py 覆盖。
        CommentPostState.objects.all().delete()

    def test_validate_comment(self):
        self.client.login(username='liangliangyy1', password='liangliangyy1')

        category = Category()
        category.name = "categoryccc"
        category.save()

        article = Article()
        article.title = "nicetitleccc"
        article.body = "nicecontentccc"
        article.author = self.user
        article.category = category
        article.type = 'a'
        article.status = 'p'
        article.save()

        comment_url = reverse(
            'comments:postcomment', kwargs={
                'article_id': article.id})

        response = self.client.post(comment_url,
                                    {
                                        'body': '123ffffffffff'
                                    })

        self.assertEqual(response.status_code, 302)

        article = Article.objects.get(pk=article.pk)
        self.assertEqual(len(article.comment_list()), 0)
        self.update_article_comment_status(article)

        self.assertEqual(len(article.comment_list()), 1)

        self.expire_post_state()
        response = self.client.post(comment_url,
                                    {
                                        'body': '123ffffffffff',
                                    })

        self.assertEqual(response.status_code, 302)

        article = Article.objects.get(pk=article.pk)
        self.update_article_comment_status(article)
        self.assertEqual(len(article.comment_list()), 2)
        parent_comment_id = article.comment_list()[0].id

        self.expire_post_state()
        response = self.client.post(comment_url,
                                    {
                                        'body': '''
                                        # Title1

        ```python
        import os
        ```

        [url](https://www.lylinux.net/)

        [ddd](http://www.baidu.com)


        ''',
                                        'parent_comment_id': parent_comment_id
                                    })

        self.assertEqual(response.status_code, 302)
        self.update_article_comment_status(article)
        article = Article.objects.get(pk=article.pk)
        self.assertEqual(len(article.comment_list()), 3)
        comment = Comment.objects.get(id=parent_comment_id)
        tree = parse_commenttree(article.comment_list(), comment)
        self.assertEqual(len(tree), 1)
        data = show_comment_item(comment, True)
        self.assertIsNotNone(data)
        s = get_max_articleid_commentid()
        self.assertIsNotNone(s)

        from comments.utils import send_comment_email
        send_comment_email(comment)
