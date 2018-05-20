#!/usr/bin/env python
# -*- coding: utf-8 -*-

import abc
import json
import datetime
import logging
import hashlib
import uuid
import scoring
from optparse import OptionParser
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class Parameter:
    __metaclass__ = abc.ABCMeta

    empty_values = (None, (), [], {}, '')

    def __init__(self, required=False, nullable=False):
        self.required = required
        self.nullable = nullable

    @abc.abstractmethod
    def validate(self, value):
        pass


class ValidationError(Exception):
    pass


class CharField(Parameter):
    def validate(self, value):
        if not isinstance(value, unicode):
            raise ValidationError("The value should be a string")


class ArgumentsField(Parameter):
    def validate(self, value):
        if not isinstance(value, dict):
            raise ValidationError("The value should consist of pairs key:value separated by comma")


class EmailField(CharField):
    def validate(self, value):
        super(EmailField, self).validate(value)
        if "@" not in value or value[-1] is "@" or value[0] is "@":
            raise ValidationError("Entered value is not a valid email")


class PhoneField(Parameter):
    def validate(self, value):
        if not isinstance(value, str) and not isinstance(value, int):
            return False
        elif not str(value).startswith("7"):
            return False
        elif len(str(value).replace('(', '').replace(')', '').replace('-', '').replace(' ', '')) != 11:
            raise ValidationError("Entered value is not a valid phone number in Russia")


class DateField(Parameter):
    def validate(self, value):
        try:
            datetime.datetime.strptime(value, '%d.%m.%Y')
        except ValueError:
            raise ValidationError("Incorrect data format, should be DD.MM.YYYY")


class BirthDayField(Parameter):
    def validate(self, value):
        super(BirthDayField, self).validate(value)
        birth_date = datetime.datetime.strptime(value, '%d.%m.%Y')
        if datetime.datetime.now().year - birth_date.year > 70:
            raise ValidationError("Incorrect birth day")


class GenderField(Parameter):
    def validate(self, value):
        if value not in GENDERS:
            raise ValidationError("Gender value should be equal to 0,1 or 2")


class ClientIDsField(Parameter):
    def validate(self, values):
        if not isinstance(values, list):
            raise ValidationError("Invalid data type, should be an array of digits")
        if not all(isinstance(v, int) and v >= 0 for v in values):
            raise ValidationError("All elements should be digits")


class MetaParameters(type):
    """Need to determine possible arguments could be given for http request and their properties via text fields
    Applied for validation incoming requests"""
    def __new__(mcs, name, bases, attributes):
        parameters = []
        for parameter_name, parameter in attributes.items():
            if isinstance(parameter, Parameter):
                parameter._name = parameter_name
                parameters.append((parameter_name, parameter))
        new_request = super(MetaParameters, mcs).__new__(mcs, name, bases, attributes)
        new_request.parameters = parameters
        return new_request


class BaseRequest(object):
    """General scheme of inheritance: abstract BaseRequest <- MethodRequest
    <- <specific request>(ClientsInterestsRequest/OnlineScoreRequest)"""
    __metaclass__ = MetaParameters

    def __init__(self, **kwargs):
        self.base_parameters = []
        self.errors = {}
        for parameter, value in kwargs.items():
            setattr(self, parameter, value)
            self.base_parameters.append(parameter)

    @abc.abstractmethod
    def validate_self(self):
        pass

    @abc.abstractmethod
    def handle(self, *request_args):
        pass


class MethodRequest(BaseRequest):
    """General request with basic parameters"""
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN

    def validate_self(self):
        for name, parameter in self.parameters:
            if name not in self.base_parameters:
                if name not in self.arguments and parameter.required:
                    self.errors[name] = "Mandatory parameter can't be omitted"
                    continue

            if name not in self.arguments:
                continue

            value = self.arguments[name]
            if value in parameter.empty_values and name is not parameter.nullable:
                self.errors[name] = "The parameter should have a value"

            try:
                parameter.validate(value)
            except ValidationError as e:
                self.errors[name] = e.message

    def handle(self, *request_args):
        pass


class ClientsInterestsRequest(MethodRequest):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)

    __choices = ["books", "tv", "music", "it", "travel", "pets"]

    def handle(self, context):
        self.validate_self()
        if self.errors:
            return self.errors, INVALID_REQUEST

        resp_body = {cid: scoring.get_interests(store=context, cid=cid) for cid in self.arguments["client_ids"]}
        context["nclients"] = len(self.arguments["client_ids"])
        return resp_body, OK


class OnlineScoreRequest(MethodRequest):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def handle(self, context):
        self.validate_self()
        if self.errors:
            return self.errors, INVALID_REQUEST

        context["has"] = self.arguments
        score = 42 if self.is_admin else scoring.get_score(store=context, phone=self.phone, email=self.email,
                                                           birthday=self.birthday, gender=self.gender,
                                                           first_name=self.first_name, last_name=self.last_name)
        return {"score": score}, OK

    def validate_self(self):
        super(OnlineScoreRequest, self).validate_self()
        if not self.errors:
            parameter_sets = [
                ("phone", "email"),
                ("first_name", "last_name"),
                ("gender", "birthday")
            ]

            if not any([all(name in self.arguments for name in parameters) for parameters in parameter_sets]):
                self.errors["arguments"] = "Invalid arguments list"


def check_auth(request):
    if request.login == ADMIN_LOGIN:
        digest = hashlib.sha512(datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).hexdigest()
    else:
        digest = hashlib.sha512(request.account + request.login + SALT).hexdigest()
    if digest == request.token:
        return True
    return False


def method_handler(request, context, ctx):
    handlers = {
        "clients_interests": ClientsInterestsRequest,
        "online_score": OnlineScoreRequest,
    }
    try:
        current_request = handlers[request["body"]["method"]](**request["body"])
    except KeyError:
        return "The request must contain the argument body", INVALID_REQUEST
    except TypeError:
        return "Invalid request format", INVALID_REQUEST
    except Exception:
        return "Unexpected error", INVALID_REQUEST

    current_request.validate_self()

    if current_request.errors:
        return current_request.errors, INVALID_REQUEST
    if not check_auth(current_request):
        return "Forbidden", FORBIDDEN

    return current_request.handle(context)


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": method_handler
    }
    store = None

    @staticmethod
    def get_request_id(headers):
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        data_string = None
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            request = json.loads(data_string)
        except:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path]({"body": request, "headers": self.headers}, context, self.store)
                except Exception, e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(filename=opts.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
