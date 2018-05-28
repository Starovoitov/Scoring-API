# -*- coding: utf-8 -*-
import hashlib
import datetime
import functools
import unittest

import RedisStore
import api


def cases(cases_):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args):
            for c in cases_:
                new_args = args + (c if isinstance(c, tuple) else (c,))
                f(*new_args)
        return wrapper
    return decorator


class TestSuite(unittest.TestCase):
    def setUp(self):
        self.context = {}
        self.headers = {}
        self.store = RedisStore.RedisStore()

    def tearDown(self):
        self.store.destroy_store()

    def get_response(self, request):
        return api.method_handler({"body": request, "headers": self.headers}, self.context, self.store)

    @staticmethod
    def set_valid_auth(request):
        if request.get("login") == api.ADMIN_LOGIN:
            request["token"] = hashlib.sha512(datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT).hexdigest()
        else:
            msg = request.get("account") + request.get("login") + api.SALT
            request["token"] = hashlib.sha512(msg).hexdigest()

    @cases([
        {},
        {"date": "20.05.2018"},
        {"client_ids": [], "date": "20.05.2018"},
        {"client_ids": {1: 2, 3: 2}, "date": "20.05.2018"},
        {"client_ids": ["1", "2"], "date": "20.05.2018"},
        {"client_ids": [1, 2], "date": "GGGG"},
    ])
    def test_invalid_interests_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code, arguments)
        self.assertTrue(len(response))

    @cases([
        {"client_ids": [1, 2, 3], "date": datetime.datetime.today().strftime("%d.%m.%Y")},
        {"client_ids": [1, 2], "date": "20.05.2018"},
        {"client_ids": [0]},
    ])
    def test_ok_interests_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, arguments)
        self.assertEqual(len(arguments["client_ids"]), len(response))
        self.assertTrue(all(v and isinstance(v, list) and all(isinstance(i, basestring) for i in v)
                            for v in response.values()))
        self.assertEqual(self.context.get("nclients"), len(arguments["client_ids"]))

    @cases([
        {},
        {"phone": "79175002040"},
        {"phone": "89175002040", "email": "stupnikov@otus.ru"},
        {"phone": "79175002040", "email": "stupnikovotus.ru"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": -1},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": "1"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.1890"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "XXX"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.2000", "first_name": 1},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.2000",
         "first_name": "s", "last_name": 2},
        {"phone": "79175002040", "birthday": "01.01.2000", "first_name": "s"},
        {"email": "stupnikov@otus.ru", "gender": 1, "last_name": 2},
    ])
    def test_invalid_score_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code, arguments)
        self.assertTrue(len(response))

    @cases([
        {"phone": "78888884444", "email": "rrrrrr@ffff.ru"},
        {"phone": 79173746784, "email": "gmail@gmail.com"},
        {"gender": 1, "birthday": "01.01.1991", "first_name": "a", "last_name": "b"},
        {"gender": 0, "birthday": "01.01.1991"},
        {"gender": 2, "birthday": "01.01.1991"},
        {"first_name": "a", "last_name": "b"},
        {"phone": "70000000000", "email": "post@yahoo.com", "gender": 1, "birthday": "01.01.1991",
         "first_name": "a", "last_name": "b"},
    ])
    def test_ok_score_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, arguments)
        score = response.get("score")
        self.assertTrue(isinstance(score, (int, float)) and score >= 0, arguments)
        self.assertEqual(sorted(self.context["has"]), sorted(arguments.keys()))

    def test_ok_score_admin_request(self):
        arguments = {"phone": "78674018665", "email": "test@test.com"}
        request = {"account": "horns&hoofs", "login": "admin", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code)
        score = response.get("score")
        self.assertEqual(score, 42)

    @cases([
        {},

        {"account": "horns&hoofs", "login": "h&f", "method": "online_score",
         "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c"
                  "03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95",
         "arguments": {}},

        {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests",
         "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c"
                  "03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95",
         "arguments": {}},
    ])
    def test_empty_request(self, request):
        _, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)

    @cases([
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score",
         "token": "48tu-jgu589u83458t53845u84589uj98j53jv58j",
         "arguments": {"phone": "73967495827", "email": "test@mail.ru", "first_name": unicode("first name"),
                       "last_name": unicode("last name"), "birthday": "01.01.1977", "gender": 1}},

        {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "token": "+++++", "arguments":
            {"client_ids": [1, 2, 3, 4, 5, 7, 8], "date": "20.05.2018"}},

        {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "token": "", "arguments":
            {"client_ids": [1], "date": "20.05.2018"}},
    ])
    def test_bad_auth(self, request):
        _, code = self.get_response(request)
        self.assertEqual(api.FORBIDDEN, code)

    @cases([
        ({"score": 5.0}, {"score": 5.0}),
        ({"score": 5.0}, {"score": 5.0}),
        ({1: ['cinema', 'tv'], 2: ['cinema', 'hi-tech'], 3: ['hi-tech', 'books']},
         {'score': 5.0, 1: ['cinema', 'tv'], 2: ['cinema', 'hi-tech'], 3: ['hi-tech', 'books']}),
        ({"score": 12.0},
         {'score': 12.0, 1: ['cinema', 'tv'], 2: ['cinema', 'hi-tech'], 3: ['hi-tech', 'books']}),
        ({1: ['cinema', 'tv'], 2: ['it', 'hi-tech']},
         {'score': 12.0, 1: ['cinema', 'tv'], 2: ['it', 'hi-tech'], 3: ['hi-tech', 'books']}),
        ({50: ['travel', 'pets'], 2: ['it', 'hi-tech']},
         {'score': 12.0, 1: ['cinema', 'tv'], 2: ['it', 'hi-tech'], 3: ['hi-tech', 'books'], 50: ['travel', 'pets']}),
    ])
    def test_update_cache(self, given, expected):
        self.store.max_cache_size = 1000
        self.store.update_cache("test_account", given)
        self.assertEqual(self.store.cache["test_account"], expected)

    @cases([
        ({"score": 5.0}, {"score": 5.0}),
        ({"score": 5.0}, {"score": 5.0}),
        ({1: ['cinema', 'tv'], 2: ['cinema', 'hi-tech'], 3: ['hi-tech', 'books']},
         {'score': 5.0, 1: ['cinema', 'tv'], 2: ['cinema', 'hi-tech'], 3: ['hi-tech', 'books']}),
        ({"score": 12.0},
         {'score': 12.0, 1: ['cinema', 'tv'], 2: ['cinema', 'hi-tech'], 3: ['hi-tech', 'books']}),
        ({1: ['cinema', 'tv'], 2: ['it', 'hi-tech']},
         {'score': 12.0, 1: ['cinema', 'tv'], 2: ['it', 'hi-tech'], 3: ['hi-tech', 'books']}),
        ({50: ['travel', 'pets'], 2: ['it', 'hi-tech']},
         {'score': 12.0, 1: ['cinema', 'tv'], 2: ['it', 'hi-tech'], 3: ['hi-tech', 'books'], 50: ['travel', 'pets']}),
    ])
    def test_update_db(self, given, expected):
        self.store.update_db(test_account=given)
        got = RedisStore.RedisStore.convert_str_to_dict(self.store.get("test_account"))
        self.assertEqual(got, expected)


if __name__ == "__main__":
    unittest.main()
