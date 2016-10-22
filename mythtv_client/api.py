import requests
from datetime import date, datetime, timedelta, time
from urllib.parse import urlencode

from .models import (
    ProgramGuide,
    RecRule,
)

from vtypes import (
    VString,
    VInt,
    VBool,
    VUnsignedInt,
    VDict,
    VList,
    VDate,
    VDateTime,
    VTime,
    Validator,
)


class API(object):
    endpoints = {}

    class Service(object):
        def __init__(self, api, endpoints):
            self.api = api
            self.endpoints = endpoints

        def __getattr__(self, endpoint):
            try:
                endpoint_cls = self.endpoints[endpoint]
            except KeyError:
                raise AttributeError('Unknown endpoint {}'.format(endpoint))
            return endpoint_cls(self.api)


    def __init__(self, url):
        self.url = url

    def __getattr__(self, service):
        try:
            endpoints = self.endpoints[service]
        except KeyError:
            raise AttributeError('Unknown service {}'.format(service))
        return self.Service(self, endpoints)

    def _request(self, service, endpoint, args, post=False):
        args = args or {}
        if post:
            url = '{url}/{service}/{endpoint}'.format(
                url=self.url,
                service=service,
                endpoint=endpoint)
        else:
            url = '{url}/{service}/{endpoint}/?{args}'.format(
                url=self.url,
                service=service,
                endpoint=endpoint,
                args=urlencode(args))
        headers = dict(Accept='application/json')

        if post:
            response = requests.post(url, data=args, headers=headers)
        else:
            response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print('Endpoint: {}/{}'.format(service, endpoint))
            from pprint import pprint
            print('###### args ########')
            pprint(args)
            print('###### content #####')
            print(response.content)
        response.raise_for_status()
        return response.json()

    @classmethod
    def register(cls, endpoint_cls):
        service = endpoint_cls.service
        endpoint = endpoint_cls.endpoint
        if service not in cls.endpoints:
            cls.endpoints[service] = {}
        cls.endpoints[service][endpoint] = endpoint_cls
        return endpoint_cls


class Endpoint(object):
    model = None
    service = None
    endpoint = None

    callable_action = 'get'
    is_post = False
    # A validator to coerce values before sending the request
    args = Validator()
    # A dict of (response-key, init-kwarg) -> Validator()
    response_args = {}

    def __init__(self, api):
        self.api = api

    def __getattr__(self, attr):
        is_get = (attr == 'get') and not self.is_post
        is_post = (attr == 'post') and self.is_post
        if is_get or is_post:
            def wrapped(**kwargs):
                return self._request(args=kwargs)
            wrapped.__name__ = attr
            return wrapped
        raise AttributeError('Unknown attribute {}'.format(attr))

    def __call__(self, *args, **kwargs):
        fn = getattr(self, self.callable_action)
        return fn(*args, **kwargs)

    def _get_args(self, args):
        validator = self.args
        return validator.to_strings(args)

    def _request(self, args=None):
        args = self._get_args(args or {})

        response = self.api._request(self.service, self.endpoint, args=args, post=self.is_post)
        if not self.is_post:
            kwargs = {}
            for (response_key, init_kwarg), validator in self.response_args.items():
                kwargs[init_kwarg] = validator.to_types(response[response_key])
            return self.model(**kwargs)


@API.register
class ProgramGuideEndpoint(Endpoint):
    model = ProgramGuide
    service = 'Guide'
    endpoint = 'GetProgramGuide'
    args = Validator(
        StartTime=VDateTime(),
        EndTime=VDateTime(),
    )
    response_args = {
        ('ProgramGuide', '_guide'): ProgramGuide.args['_guide'],
    }


@API.register
class GetRecordSchedule(Endpoint):
    service = 'Dvr'
    endpoint = 'GetRecordSchedule'
    model = RecRule
    args = Validator(
        StartTime=VDateTime(),
        ChanId=VInt(),
        RecordId=VInt(default=0, settable=False),
        Template=VString(default='', settable=False),
        MakeOverride=VInt(default=0, settable=False),
    )
    response_args = {
        ('RecRule', '_recrule'): RecRule.args['_recrule'],
    }


@API.register
class AddRecordSchedule(Endpoint):
    service = 'Dvr'
    endpoint = 'AddRecordSchedule'
    callable_action = 'record'
    is_post = True
    # Validation for this is nearly-but-not-quite the same as the
    # validation for a RecRule.
    args = (
        RecRule.validator.remove(
            'LastDeleted',
            'LastRecorded',
            'NextRecording',
            'CallSign',
            'Id',
            'AverageDelay',
            'SubTitle',
        ).add(
            Station=VString(),
            Subtitle=VString()
        )
    )

    def record(self, program):
        schedule = self.api.Dvr.GetRecordSchedule(
            StartTime=program.StartTime,
            ChanId=program.ChanId)
        args = schedule._recrule
        args['Type'] = 'Single Record'
        args['Filter'] = '1024'
        args['Station'] = args['CallSign']
        args['Subtitle'] = args['SubTitle']
        remove_keys = (
            'SubTitle',
            'LastRecorded',
            'NextRecording',
            'AverageDelay',
            'CallSign',
            'Id',
            'LastDeleted',
        )
        for remove_key in remove_keys:
            del args[remove_key]
        self.post(**args)
