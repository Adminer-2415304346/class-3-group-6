# SZX（第7—8周）：继承 Haystack 搜索表单；querydata 是额外必填字段，需核对调用模板。
import logging

from django import forms
from haystack.forms import SearchForm

logger = logging.getLogger(__name__)


class BlogSearchForm(SearchForm):
    querydata = forms.CharField(required=True)

    def search(self):
        # SZX（第7—8周）：先委托父类生成检索，再检查本表单；非法输入返回空查询结果。
        datas = super(BlogSearchForm, self).search()
        if not self.is_valid():
            return self.no_query_found()

        if self.cleaned_data['querydata']:
            logger.info(self.cleaned_data['querydata'])
        return datas
