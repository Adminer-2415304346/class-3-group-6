"""SZX：只读导出当前 Django 模型和迁移元数据，不读取业务记录或更改数据库。"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src' / 'DjangoBlog'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoblog.settings')

import django

django.setup()

from django.apps import apps
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.models import NOT_PROVIDED


def field_metadata(field):
    default = field.default
    if default is NOT_PROVIDED:
        default = None
    elif callable(default):
        default = default.__module__ + '.' + default.__name__
    return {
        'name': field.name,
        'column': field.column,
        'type': field.__class__.__name__,
        'sql_type': None if field.many_to_many else field.db_type(connection),
        'max_length': field.max_length,
        'primary_key': field.primary_key,
        'unique': field.unique,
        'null': field.null,
        'blank': field.blank,
        'has_default': field.default is not NOT_PROVIDED,
        'default': default,
        'choices': [[str(key), str(label)] for key, label in field.choices] if field.choices else [],
        'relation_model': field.related_model._meta.label if field.is_relation else None,
        'relation_table': field.remote_field.through._meta.db_table if field.many_to_many else None,
        'on_delete': field.remote_field.on_delete.__name__ if field.many_to_one else None,
        'many_to_many': field.many_to_many,
        'auto_now_add': getattr(field, 'auto_now_add', False),
        'auto_now': getattr(field, 'auto_now', False),
    }


def inspect_models():
    state = MigrationLoader(None).project_state()
    result = []
    for app_label in ('accounts', 'blog', 'comments', 'oauth'):
        for model in apps.get_app_config(app_label).get_models():
            migrated = state.apps.get_model(model._meta.label)
            item = {
                'label': model._meta.label,
                'table': model._meta.db_table,
                'ordering': list(model._meta.ordering),
                'unique_together': model._meta.unique_together,
                'indexes': [{'name': index.name, 'fields': index.fields} for index in model._meta.indexes],
                'fields': [],
                'many_to_many': [],
            }
            for field in model._meta.concrete_fields:
                metadata = field_metadata(field)
                metadata['migration_type'] = migrated._meta.get_field(field.name).__class__.__name__
                item['fields'].append(metadata)
            for field in model._meta.local_many_to_many:
                metadata = field_metadata(field)
                through = field.remote_field.through
                metadata['through_fields'] = [field_metadata(f) for f in through._meta.concrete_fields]
                metadata['unique_together'] = through._meta.unique_together
                item['many_to_many'].append(metadata)
            result.append(item)
    return result


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print('MODEL_METADATA=' + json.dumps(inspect_models(), ensure_ascii=False))
