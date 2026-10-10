from django.db import migrations


def rename_demo_categories(apps, schema_editor):
    Category = apps.get_model('blog', 'Category')

    parent = Category.objects.filter(
        name='我是父类目',
        parent_category__isnull=True,
    ).first()
    if parent is None:
        return

    parent_id = parent.pk
    if Category.objects.exclude(pk=parent_id).filter(name='技术专栏').exists():
        return

    Category.objects.filter(pk=parent_id).update(
        name='技术专栏',
        slug='ji-zhu-zhuan-lan',
    )

    child = Category.objects.filter(
        name='子类目',
        parent_category_id=parent_id,
    ).first()
    if child and not Category.objects.exclude(pk=child.pk).filter(name='Django 开发').exists():
        Category.objects.filter(pk=child.pk).update(
            name='Django 开发',
            slug='django-kai-fa',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0008_blogsettings_color_scheme'),
    ]

    operations = [
        migrations.RunPython(rename_demo_categories, migrations.RunPython.noop),
    ]
