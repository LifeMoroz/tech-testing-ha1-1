# -*- coding:  utf-8 -*-
__author__ = 'Ruslan'

import unittest
import re

from bs4 import BeautifulSoup
import mock

from source.lib import REDIRECT_HTTP, REDIRECT_META, get_redirect_history
from source.lib import to_unicode, get_counters, fix_market_url, PREFIX_GOOGLE_MARKET, prepare_url, get_url, \
    ERROR_REDIRECT, make_pycurl_request, to_str, check_for_meta


class TestInit(unittest.TestCase):
    def setUp(self):
        self.small_timeout = 1
        self.normal_timeout = 10
        self.big_timeout = 60

    def tearDown(self):
        pass

    def test_to_unicode_with_unicode_str(self):
        """
        Сразу передаем UNICODE
        :return:
        """
        val = u'unicode string'
        result = to_unicode(val)
        is_unicode = isinstance(result, unicode)
        self.assertTrue(is_unicode)

    def test_to_unicode_with_not_unicode_str(self):
        """
        Передаем ASCII
        :return:
        """
        val = 'ascii string'
        result = to_unicode(val)
        is_unicode = isinstance(result, unicode)
        self.assertTrue(is_unicode)

    def test_to_str_with_unicode(self):
        """
        Передаем UNICODE
        :return:
        """
        val = u'unicode string'
        result = to_str(val)
        is_str = isinstance(result, str)
        self.assertTrue(is_str)

    def test_to_str_with_ascii(self):
        """
        Передаем ASCII
        :return:
        """
        val = 'ascii string'
        result = to_str(val)
        is_str = isinstance(result, str)
        self.assertTrue(is_str)

# Get_counters не обрабатывает None
    def test_get_counters_with_no_counters(self):
        """
        в контенте нет ссылок на счетчики
        :return:
        """
        assert get_counters("content without counters") == []

    def test_get_counters_with_counters(self):
        """
        в контенте есть ссылки на счетчики
        :return:
        """
        test_counter_list = [{'counter': 'GOOGLE_ANALYTICS', 'content': 'google-analytics.com/ga.js'},
                             {'counter': 'YA_METRICA', 'content': 'mc.yandex.ru/metrika/watch.js'}]
        self.assertEquals(get_counters(''.join([i['content'] for i in test_counter_list])),
                          [i['counter'] for i in test_counter_list])

# fix_market_url не проверяет что ему прилетел маркет урл, а так же не проверяет что элемент не None
    def test_fix_market_url(self):
        """
        преобразование ссылки на маркет
        :return:
        """
        market = "details?id=12345"
        market_url = PREFIX_GOOGLE_MARKET + market
        self.assertEquals(fix_market_url('market://' + market), market_url)

    def test_prepare_none_url(self):
        """
        url = None
        :return:
        """
        url = None
        self.assertEqual(prepare_url(url), url)

    def test_prepare_url_with_no_exception(self):
        """
        при кодировании в idna не вылетает exception
        :return:
        """
        my_mock = mock.MagicMock()
        with mock.patch('source.lib.urlparse', mock.Mock(return_value=[my_mock] * 6)), \
             mock.patch('source.lib.logger', mock.MagicMock()) as logger:
            prepare_url('url')
            my_mock.encode.assert_called_once()
            assert not logger.error.called

    def test_prepare_url_with_exception(self):
        """
        при кодировании в idna вылетает exception
        :return:
        """
        url = 'url'
        new_mock = mock.MagicMock()
        new_mock.encode.side_effect = UnicodeError("unicode error")
        urlparse_m = mock.Mock(return_value=[new_mock] * 6)
        with mock.patch('source.lib.urlparse', urlparse_m):
            try:
                prepare_url(url)
            except UnicodeError:
                self.fail('UnicodeError not caught in prepare_url()')

# make_pycurl_request не проверяет аргументы на None, или если url не string, то все красиво упадет ^^
    def _make_pycurl_request(self, redirect_url, test_resp, url='example.net',
                             useragent=None, curl_mock=mock.MagicMock()):
        string_io_mock = mock.Mock(return_value=test_resp)
        curl_mock.getinfo = mock.Mock(return_value=redirect_url)
        curl_mock.setopt = mock.Mock()
        with mock.patch('source.lib.to_str', mock.Mock(return_value=url)), \
                mock.patch('source.lib.to_unicode', mock.Mock(return_value=redirect_url)), \
                mock.patch('StringIO.StringIO.getvalue', string_io_mock), \
                mock.patch('pycurl.Curl', mock.Mock(return_value=curl_mock)):
            return make_pycurl_request(url, self.big_timeout, useragent)

    @mock.patch('source.lib.prepare_url', mock.Mock())
    def test_make_pycurl_request(self):
        """
        Сделать обычный запрос
        """
        test_resp = 'response from example.net'
        redirect_url = 'http://another_url.org'
        useragent = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:32.0) Gecko/20100101 Firefox/32.0'
        curl_m = mock.MagicMock()
        response, redirect = self._make_pycurl_request(redirect_url, test_resp, useragent=useragent,
                                                       curl_mock=curl_m)
        self.assertEqual(response, test_resp, 'Wrong response')
        self.assertEqual(redirect, redirect_url, 'Wrong redirect url')
        curl_m.setopt.assert_any_call(curl_m.USERAGENT, useragent)

    @mock.patch('source.lib.prepare_url', mock.Mock())
    def test_make_pycurl_request_no_useragent(self):
        """
        Не передан useragent
        :return:
        """
        resp_test = 'hello from test_url.net'
        redirect_url = 'http://another_url.org'
        response, redirect = self._make_pycurl_request(redirect_url, resp_test)
        self.assertEqual(response, resp_test, 'Wrong response')
        self.assertEqual(redirect, redirect_url, 'Wrong redirect url')

    @mock.patch('source.lib.prepare_url', mock.Mock())
    def test_make_pycurl_request_without_redirect_url(self):
        """
        В ответе нет redirect url
        :return:
        """
        resp_test = 'hello from test_url.net'
        redirect_url = None
        response, redirect = self._make_pycurl_request(redirect_url, resp_test)
        self.assertEqual(response, resp_test, 'Wrong response')
        self.assertEqual(redirect, redirect_url, 'Wrong redirect url')

#Аналогично make_pycurl_request
    def test_get_url_error_redirect(self):
        """
        get_url возвращает тип редиректа ERROR
        :return:
        """
        url = "url"
        with mock.patch('source.lib.make_pycurl_request', mock.Mock(side_effect=ValueError('value error'))):
            self.assertEquals(get_url(url, timeout=self.normal_timeout), (url, ERROR_REDIRECT, None))

    def test_get_url_ok_redirect(self):
        """
        Пропускает ok login redirects
        :return:
        """
        url = "url"
        new_redirect_url = "http://odnoklassniki.ru/123.st.redirect"
        content = "content"
        with mock.patch('source.lib.make_pycurl_request', mock.Mock(return_value=(content, new_redirect_url))):
            self.assertEquals(get_url(url, timeout=self.normal_timeout), (None, None, content))

    def _get_url_redirect(self, new_redirect_url, make_py_curl_request_return, prepare_url_return, check_meta_return):
        with mock.patch('source.lib.fix_market_url', mock.Mock()) as fix_market_url, \
            mock.patch('source.lib.make_pycurl_request', mock.Mock(return_value=make_py_curl_request_return)), \
            mock.patch('source.lib.check_for_meta', mock.Mock(return_value=check_meta_return)), \
            mock.patch('source.lib.prepare_url', mock.Mock(return_value=prepare_url_return)) as m_prepare_url:
            return get_url(new_redirect_url, timeout=self.normal_timeout), fix_market_url, m_prepare_url

    def test_get_url_market_url_redirect_http(self):
        """
        redirect type is HTTP
        """
        new_redirect_url = "market://android.ru/details?id=12345"
        prepare_url_return = "returned by prepare_url(new_redirect_url)"
        content = "content"
        get_url_return, m_fix_market, m_prepare_url = self._get_url_redirect(
            new_redirect_url, make_py_curl_request_return=(content, new_redirect_url),
            prepare_url_return=prepare_url_return, check_meta_return=None)
        self.assertEquals(get_url_return, (prepare_url_return, REDIRECT_HTTP, content))
        m_fix_market.assert_called_once_with(new_redirect_url)

    def test_get_url_redirect_url_and_redirect_type_are_none(self):
        """
        redirect url is none
        return null redirect type
        :return:
        """
        new_redirect_url = None
        prepare_url_return = None
        content = 'content'
        get_url_return, m_fix_market, m_prepare_url = self._get_url_redirect(
            new_redirect_url, make_py_curl_request_return=(content, new_redirect_url),
            prepare_url_return=prepare_url_return, check_meta_return=None)
        self.assertEquals((prepare_url_return, None, content), get_url_return)
        self.assertFalse(m_fix_market.called)
        m_prepare_url.assert_called_once_with(new_redirect_url)

    def test_get_url_meta_redirect_type_with_redirect_url_none(self):
        """
        redirect url is none при make_pycurl_request
        return meta redirect type
        :return:
        """
        prepare_url_return = new_redirect_url = "not none redirect url"
        content = 'content'
        get_url_return, m_fix_market, m_prepare_url = self._get_url_redirect(
            new_redirect_url, make_py_curl_request_return=(content, None),
            prepare_url_return=prepare_url_return, check_meta_return=new_redirect_url)
        self.assertEquals((prepare_url_return, REDIRECT_META, content), get_url_return)
        self.assertFalse(m_fix_market.called)
        m_prepare_url.assert_called_once_with(new_redirect_url)

#get_redirect_history не проверяются входные параметры
    def test_get_redirect_history_mymail(self):
        """
        правильные возвращаемые значения для my.mail
        :return:
        """
        m_url = 'https://my.mail.ru/apps/'
        self.assertEquals(([], [m_url], []), get_redirect_history(url=m_url, timeout=self.small_timeout), "invalid")

    def test_get_redirect_history_odnoklassniki(self):
        """
        правильные возвращаемые значения для odnoklassniki
        :return:
        """
        o_url = 'https://odnoklassniki.ru/'
        self.assertEquals(([], [o_url], []), get_redirect_history(url=o_url, timeout=self.small_timeout), "invalid")

    def test_get_redirect_history_redirect_url_none_counters_none(self):
        """
        правильные возвращаемые значения для redirect_url = None и content = None
        :return:
        """
        url = "http://url.ru"
        redirect_url = redirect_type = content = None
        with mock.patch('source.lib.get_url', mock.Mock(return_value=(redirect_url, redirect_type, content))):
            self.assertEquals(([], [url], []), get_redirect_history(url=url, timeout=self.small_timeout),
                              "invalid returned values")

    def test_get_redirect_history_redirect_type_error(self):
        """
        with redirect type ERROR_REDIRECT
        """
        url = "http://example.ru"
        redirect_url = "http://redirect.url"
        redirect_type = ERROR_REDIRECT

        with mock.patch('source.lib.get_url',
                        mock.Mock(return_value=(redirect_url, redirect_type, 'google-analytics.com/ga.js'))):
            self.assertEquals(([redirect_type], [url, redirect_url], ["GOOGLE_ANALYTICS"]),
                              get_redirect_history(url=url, timeout=self.small_timeout), "invalid returned values")

    def test_redirect_one(self):
        """
        только 1 редирект
        :return:
        """
        url = "http://example.ru"
        redirect_url = "http://redirect.url"
        redirect_type = "type"

        with mock.patch('source.lib.get_url', mock.Mock(return_value=(redirect_url, redirect_type, None))):
            self.assertEquals(([redirect_type], [url, redirect_url], []),
                              get_redirect_history(url=url, timeout=self.small_timeout, max_redirects=1),
                              "invalid returned values")

    def _prepare_mock(self):
        m = mock.MagicMock(name="result")
        m.attrs = {
            "content": True,
            "http-equiv": "refresh"
        }
        return m

    def test_check_for_meta_with_content_split_bad(self):
        """
        В контенте не 2 параметра
        :return:
        """
        result = self._prepare_mock()
        result.__getitem__ = mock.Mock(return_value="content")
        with mock.patch.object(re, 'search', mock.Mock()) as research, \
                mock.patch.object(BeautifulSoup, 'find', return_value=result):
            check_for_meta("content", "url")
            self.assertFalse(research.called)

    def test_check_for_meta_correct(self):
        """
        Весь путь в check_for_meta
        :return:
        """
        url = "localhost/lal?what_are_you_doing=dont_know"
        result = self._prepare_mock()
        result.__getitem__ = mock.Mock(return_value="wait;url=" + url)
        with mock.patch.object(BeautifulSoup, 'find', return_value=result):
            check = check_for_meta("content", "url")
            self.assertEquals(check, url)

    def test_check_for_meta_no_meta(self):
        """
        find("meta") returns None
        """
        ret = None
        with mock.patch.object(BeautifulSoup, 'find', return_value=ret):
            check = check_for_meta("content", "url")
            self.assertIsNone(check)

    def test_check_for_meta_without_httpequiv_attr(self):
        """
        http-equiv unspecified
        """
        result = mock.MagicMock(name="result")
        result.attrs = {
            "content": True,
        }
        with mock.patch.object(BeautifulSoup, 'find', return_value=result):
            check = check_for_meta("content", "url")
            self.assertIsNone(check)

    def test_check_for_meta_httpequiv_no_refresh(self):
        """
        http-equiv is /no refresh/
        """
        result = mock.MagicMock(name="result")
        result.attrs = {
            "content": True,
            'http-equiv': "no refresh"
        }
        with mock.patch.object(BeautifulSoup, 'find', return_value=result):
            check = check_for_meta("content", "url")
            self.assertIsNone(check)
