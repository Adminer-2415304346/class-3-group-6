# SZX（第7—8周）：定义Elasticsearch文章和耗时文档；管理器方法会访问索引，不能当纯数据转换模块运行。
import time

import elasticsearch.client
from django.conf import settings
from elasticsearch_dsl import Document, InnerDoc, Date, Integer, Long, Text, Object, GeoPoint, Keyword, Boolean
from elasticsearch_dsl.connections import connections

from blog.models import Article

# SZX（第7—8周）：此标志只表示配置存在，不代表ES可用；连接参数也仅在启用分支中创建。
ELASTICSEARCH_ENABLED = hasattr(settings, 'ELASTICSEARCH_DSL')

if ELASTICSEARCH_ENABLED:
    from elasticsearch import Elasticsearch

    es_config = settings.ELASTICSEARCH_DSL['default']

    # 处理 hosts 配置，确保有 scheme
    hosts = es_config['hosts']
    if isinstance(hosts, str):
        # 如果没有 scheme，自动添加 http://
        if not hosts.startswith(('http://', 'https://')):
            hosts = f'http://{hosts}'
        hosts = [hosts]
    elif isinstance(hosts, list):
        # 处理列表中的每个 host
        processed_hosts = []
        for host in hosts:
            if not host.startswith(('http://', 'https://')):
                host = f'http://{host}'
            processed_hosts.append(host)
        hosts = processed_hosts

    # ES 连接配置（动态适配认证方式）
    es_params = {
        'hosts': hosts,
        'verify_certs': es_config.get('verify_certs', False),
    }

    # 支持用户名密码认证（ES 8.x 默认启用安全特性）
    if 'username' in es_config and 'password' in es_config:
        es_params['basic_auth'] = (es_config['username'], es_config['password'])

    # 支持 API Key 认证
    if 'api_key' in es_config:
        es_params['api_key'] = es_config['api_key']

    # 支持证书认证
    if 'ca_certs' in es_config:
        es_params['ca_certs'] = es_config['ca_certs']

    # 支持客户端证书
    if 'client_cert' in es_config and 'client_key' in es_config:
        es_params['client_cert'] = es_config['client_cert']
        es_params['client_key'] = es_config['client_key']

    # 创建连接
    es = Elasticsearch(**es_params)
    connections.create_connection(**es_params)

    # SZX（第7—8周）：启用ES时导入即查询GeoIP管道，缺失则创建；这里只捕获NotFoundError。
    # 设置 GeoIP pipeline
    try:
        es.ingest.get_pipeline(id='geoip')
    except elasticsearch.exceptions.NotFoundError:
        es.ingest.put_pipeline(id='geoip', body={
            "description": "Add geoip info",
            "processors": [
                {
                    "geoip": {
                        "field": "ip"
                    }
                }
            ]
        })


class GeoIp(InnerDoc):
    continent_name = Keyword()
    country_iso_code = Keyword()
    country_name = Keyword()
    location = GeoPoint()


class UserAgentBrowser(InnerDoc):
    Family = Keyword()
    Version = Keyword()


class UserAgentOS(UserAgentBrowser):
    pass


class UserAgentDevice(InnerDoc):
    Family = Keyword()
    Brand = Keyword()
    Model = Keyword()


class UserAgent(InnerDoc):
    browser = Object(UserAgentBrowser, required=False)
    os = Object(UserAgentOS, required=False)
    device = Object(UserAgentDevice, required=False)
    string = Text()
    is_bot = Boolean()


class ElapsedTimeDocument(Document):
    url = Keyword()
    time_taken = Long()
    log_datetime = Date()
    ip = Keyword()
    geoip = Object(GeoIp, required=False)
    useragent = Object(UserAgent, required=False)

    class Index:
        name = 'performance'
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }


class ElaspedTimeDocumentManager:
    # SZX（第7—8周）：检查performance索引，不存在才初始化；调用者须有ES配置和可用连接。
    @staticmethod
    def build_index():
        from elasticsearch import Elasticsearch
        # 使用已配置好的连接参数
        client = Elasticsearch(**es_params)
        res = client.indices.exists(index="performance")
        if not res:
            ElapsedTimeDocument.init()

    # SZX（第7—8周）：删除整个performance索引及其耗时记录；忽略不存在，不屏蔽连接或权限异常。
    @staticmethod
    def delete_index():
        from elasticsearch import Elasticsearch
        es = Elasticsearch(**es_params)
        try:
            es.indices.delete(index='performance')
        except elasticsearch.exceptions.NotFoundError:
            pass

    # SZX（第7—8周）：将请求URL、毫秒耗时、时间、UA及IP写入ES，返回值为空，属于持久化副作用。
    @staticmethod
    def create(url, time_taken, log_datetime, useragent, ip):
        ElaspedTimeDocumentManager.build_index()
        ua = UserAgent()
        ua.browser = UserAgentBrowser()
        ua.browser.Family = useragent.browser.family
        ua.browser.Version = useragent.browser.version_string

        ua.os = UserAgentOS()
        ua.os.Family = useragent.os.family
        ua.os.Version = useragent.os.version_string

        ua.device = UserAgentDevice()
        ua.device.Family = useragent.device.family
        ua.device.Brand = useragent.device.brand
        ua.device.Model = useragent.device.model
        ua.string = useragent.ua_string
        ua.is_bot = useragent.is_bot

        # SZX（第7—8周）：文档ID取当前毫秒；同毫秒并发写入不能据此保证唯一，保存还会调用GeoIP管道。
        doc = ElapsedTimeDocument(
            meta={
                'id': int(
                    round(
                        time.time() *
                        1000))
            },
            url=url,
            time_taken=time_taken,
            log_datetime=log_datetime,
            useragent=ua, ip=ip)
        doc.save(pipeline="geoip")


# SZX（第7—8周）：文章索引冗余作者、分类和标签；IK分析器是ES部署依赖，不是Whoosh的分词配置。
class ArticleDocument(Document):
    body = Text(analyzer='ik_max_word', search_analyzer='ik_smart')
    title = Text(analyzer='ik_max_word', search_analyzer='ik_smart')
    author = Object(properties={
        'nickname': Text(analyzer='ik_max_word', search_analyzer='ik_smart'),
        'id': Integer()
    })
    category = Object(properties={
        'name': Text(analyzer='ik_max_word', search_analyzer='ik_smart'),
        'id': Integer()
    })
    tags = Object(properties={
        'name': Text(analyzer='ik_max_word', search_analyzer='ik_smart'),
        'id': Integer()
    })

    pub_time = Date()
    status = Text()
    comment_status = Text()
    type = Text()
    views = Integer()
    article_order = Integer()

    class Index:
        name = 'blog'
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }


class ArticleDocumentManager():

    # SZX（第7—8周）：实例化即初始化索引映射，构造对象会联网；并非等到搜索时才访问ES。
    def __init__(self):
        self.create_index()

    # SZX（第7—8周）：初始化或更新blog索引映射；该方法自身不删除索引，也不装载文章。
    def create_index(self):
        ArticleDocument.init()

    # SZX（第7—8周）：删除整个blog索引；只容忍索引不存在，命令重建失败时不会自动恢复原索引。
    def delete_index(self):
        from elasticsearch import Elasticsearch
        es = Elasticsearch(**es_params)
        try:
            es.indices.delete(index='blog')
        except elasticsearch.exceptions.NotFoundError:
            pass

    # SZX（第7—8周）：将传入文章转成文档列表，不写ES；读取作者、分类、标签时仍可能触发ORM查询。
    def convert_to_doc(self, articles):
        return [
            ArticleDocument(
                meta={
                    'id': article.id},
                body=article.body,
                title=article.title,
                author={
                    'nickname': article.author.username,
                    'id': article.author.id},
                category={
                    'name': article.category.name,
                    'id': article.category.id},
                tags=[
                    {
                        'name': t.name,
                        'id': t.id} for t in article.tags.all()],
                pub_time=article.pub_time,
                status=article.status,
                comment_status=article.comment_status,
                type=article.type,
                views=article.views,
                article_order=article.article_order) for article in articles]

    # SZX（第7—8周）：初始化映射后逐篇保存；本方法不负责先删除旧索引，也没有批量事务回滚。
    def rebuild(self, articles=None):
        ArticleDocument.init()
        # SZX（第7—8周）：空集合也回退全部文章，不筛发布态/类型。
        articles = articles if articles else Article.objects.all()
        docs = self.convert_to_doc(articles)
        for doc in docs:
            doc.save()

    # SZX（第7—8周）：逐个保存传入文档，按相同ID覆盖；发生异常前已保存的文档不会自动回滚。
    def update_docs(self, docs):
        for doc in docs:
            doc.save()
