from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from requests import Request as HTTPRequest, Session
from requests.cookies import create_cookie, RequestsCookieJar
from urllib.parse import parse_qs, urlparse, urlencode
from requests_toolbelt.utils import dump

from model_utils.models import TimeStampedModel

from smithy.helpers import render_with_context, parse_dump_result


class NameValueModel(TimeStampedModel):
    name = models.CharField(max_length = 200)
    value = models.TextField(blank = True)

    def __str__(self):
        return self.name

    class Meta:
        abstract = True


class Request(TimeStampedModel):
    
    METHODS = (
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
        ('OPTIONS', 'OPTIONS'),
        ('HEAD', 'HEAD'),
    )
    BODY_TYPES = (
        ('', 'Other'),
        ('application/x-www-form-urlencoded', 'x-www-form-urlencoded'),
        ('application/json', 'JSON'),
        ('text/plain', 'Text'),
        ('application/javascript', 'JavaScript'),
        ('application/xml', 'XML (application/xml)'),
        ('text/xml', 'XML (text/xml)'),
        ('text/html', 'HTML'),
    )
    method = models.CharField(
        max_length = 7, choices = METHODS,
        blank = False, null = False)
    name = models.CharField(max_length = 500, blank = False)
    url = models.CharField(max_length = 2083)
    body = models.TextField(blank = True)
    content_type = models.CharField(
        default = BODY_TYPES[0][0],
        blank = True, null = True,
        max_length = 100, choices = BODY_TYPES)

    def __str__(self):
        if self.name:
            return self.name
        return "{} {}".format(
            self.method,
            self.url,
        )


class RequestBlueprint(Request):
    
    follow_redirects = models.BooleanField(
        default = False, blank = False, null = False)

    @property
    def name_value_related(self):
        return [
            self.headers,
            self.query_parameters,
            self.cookies
        ]

    def send(self, context = None):

        context = context or {}
        for variable in self.variables.all():
            context[variable.name] = variable.value

        request = HTTPRequest(
            url = render_with_context(self.url, context),
            method = self.method)

        session = Session()
        record = RequestRecord.objects.create(blueprint = self)

        
        for qs in self.name_value_related:
            for obj in qs.all():
                obj.pk = 0
                obj.name = render_with_context(obj.name, context)
                obj.value = render_with_context(obj.value, context)
                obj.add_to(request)
                obj.request = record
                obj.save()

        if self.content_type == self.BODY_TYPES[0][0]:
            data = render_with_context(self.body, context)
        else:
            data = {}
            for param in self.body_parameters.all():
                param.add_to(data, context)

        request.data = data
        prepared_request = request.prepare()

        response = session.send(prepared_request, stream = True)
        # TODO: follow redirects

        RequestRecord.objects.filter(pk = record.pk).update(
            raw_request = parse_dump_result(dump._dump_request_data, prepared_request),
            raw_response = parse_dump_result(dump._dump_response_data, response),
            status = response.status_code,
            **RequestRecord.get_clone_args(self, context)
        )

        
        return RequestRecord.objects.get(pk = record.pk)


class RequestRecord(Request):
   
    raw_request = models.TextField()
    raw_response = models.TextField()
    status = models.PositiveIntegerField(null = True)
    blueprint = models.ForeignKey(
        'smithy.RequestBlueprint',
        on_delete = models.SET_NULL,
        null = True)

    @property
    def is_success(self):
        return self.status and self.status < 400

    @staticmethod
    def of_blueprint(blueprint):
        return RequestRecord.objects.filter(
            blueprint = blueprint)

    @classmethod
    def get_clone_args(cls, obj, context : dict):
        return dict([
            (
                render_with_context(fld.name, context),
                render_with_context(getattr(obj, fld.name), context)
            )
            for fld \
            in cls._meta.fields \
            if fld.name != obj._meta.pk \
            and fld in obj._meta.fields \
            and fld.name not in [
                   'request', 'id', 'created', 'updated'
               ]])
