__author__ = 'Ruslan'
import unittest
import mock
from mock import patch, Mock

from source.lib import utils


class DaemonizeTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _daemonize(self, m_setsid=Mock(), m_exit=Mock(), m_fork=Mock(return_value=42)):
        with patch('os.fork', m_fork), patch('os._exit', m_exit) as mock_os_exit,\
                mock.patch('os.setsid', m_setsid):
            utils.daemonize()

        return mock_os_exit

    def test_parent_daemonize_correct(self):
        """
        first try_pid returns >0
        """
        mock_os_exit = self._daemonize(m_setsid=Mock(), m_exit=Mock())
        mock_os_exit.assert_called_once_with(0)

    def test_parent_daemonize_with_exception(self):
        """
        first try_pid exits with exception
        """
        self.assertRaises(Exception, self._daemonize, m_fork=Mock(side_effect=OSError("Hello from core!!!")))

    def test_daemonize_child_correct(self):
        """
        first try_pid returns 0 0
        second try_pid returns > 0
        """
        mock_os_exit = self._daemonize(m_exit=Mock(side_effect=None),  m_fork=Mock(side_effect=[0, 42]))
        mock_os_exit.assert_called_once_with(0)

    def test_daemonize_child_with_exception(self):
        """
        first try_pid returns 0
        second try_pid exits with exception
        """
        self.assertRaises(Exception, self._daemonize, m_fork=Mock(side_effect=[0, OSError("Hello from core!!!")]))

    def test_daemonize_pid_0(self):
        """
        first try_pid returns 0
        second try_pid returns 0
        """
        mock_os_exit = self._daemonize(m_fork=Mock(return_value=0))
        self.assert_(mock_os_exit.not_called)

    def test_daemonize_parentpid_0_with_setsid_exception(self):
        """
        first try_pid returns 0
        second setsid exits with exception
        """
        self.assertRaises(Exception, self._daemonize, m_fork=Mock(return_value=0), m_exit=Mock(side_effect=None),
                          m_setsid=Mock(side_effect=OSError("Hello from core!!!")))


class CreatePidFileTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _create_pidfile(self, m_open, m_getpid):
        with patch('__builtin__.open', m_open, create=True) as mock_open, patch('os.getpid', m_getpid):
            utils.create_pidfile('/file/path')
        return mock_open

    def test_create_pidfile(self):

        pid = 24
        m_open = mock.mock_open()
        self._create_pidfile(m_open,  Mock(return_value=pid))
        m_open.assert_called_once_with('/file/path', 'w')
        m_open().write.assert_called_once_with(str(pid))

    def test_writefile_exception(self):
        """
        IOError while writing file
        """
        self.assertRaises(IOError, self._create_pidfile, Mock(side_effect=IOError("Can't write to a file")),
                          Mock(return_value=24))


class LoadConfigFromPyfileTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_wrong_config_filepath(self):
        self.assertRaises(IOError, utils.load_config_from_pyfile, 'wrong/path')

    def test_load_config_file_correct(self):
        """
        Test correct work
        """
        import os

        variables = {
            'QUEUE_PORT': '33013',
            'QUEUE_SPACE': '0'
        }
        with patch('source.lib.utils.execfile_wrapper', Mock(return_value=variables)):
            var = utils.load_config_from_pyfile(os.path.realpath(os.path.expanduser("source/tests/config/ok.py")))

        real_config = utils.Config()
        real_config.QUEUE_PORT, real_config.QUEUE_SPACE = (variables['QUEUE_PORT'], variables['QUEUE_SPACE'])
        self.assertEquals((var.QUEUE_PORT, var.QUEUE_SPACE), (real_config.QUEUE_PORT, real_config.QUEUE_SPACE))

    def test_load_config_file_failed(self):
        """
        Test correct work with bad config
        """
        import os

        variables = {
            'QUEUE_PORT': '',
            'Wrong_attribute': '0'
        }
        with patch('source.lib.utils.execfile_wrapper', Mock(return_value=variables)):
            returns = utils.load_config_from_pyfile(
                os.path.realpath(os.path.expanduser('source/tests/test_config_bad')))
        with self.assertRaises(AttributeError):
            getattr(returns, 'Wrong_attribute')


class SpawnWorkersTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_spawn_workers(self):
        """
        Test correct work
        """
        args = []
        num = 10
        with patch('multiprocessing.process.Process.start', mock.MagicMock()) as mock_process:
            utils.spawn_workers(num, "target", args, num)
            self.assertTrue(mock_process.called)
            self.assertEqual(mock_process.call_count, num)

    def test_spawn_workers_fail(self):
        """
        Test work with num 0
        """
        args = []
        num = 0
        with patch('multiprocessing.Process', Mock()) as mock_process:
            utils.spawn_workers(num, "target", args, num)
            self.assertFalse(mock_process.called)


class ForOneTestTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_parse_cmd_args_exist(self):
        """
        Test correct work with existing cmd params
        """
        app_description = "this is description"
        parameters = ['-d', '--config', '-P', app_description]
        parser = Mock()
        with patch('argparse.ArgumentParser', Mock(return_value=parser)):
            utils.parse_cmd_args(parameters)
            parser.parse_args.assert_called_once_with(args=parameters)

    def test_get_tube(self):
        """
        Test correct work
        """
        name = 'This_is_my_real_name_!!!'
        port = 8080
        host = '127.0.0.1'
        space = 42
        queue = mock.MagicMock()

        with patch('tarantool_queue.Queue', Mock(return_value=queue.tube(name))):
            utils.get_tube(host, port, space, name)
        queue.asser_called_once_with(host, port, space, name)

    def test_network_status_ok(self):
        """
        Test correct work
        """
        check_url = Mock()
        timeout = 0
        with patch('urllib2.urlopen', Mock(return_value=True)) as urllib:
            utils.check_network_status(check_url, timeout)
            urllib.assert_call_once_with(check_url, timeout)

    def test_network_status_fail(self):
        """
        Test work with exception
        """
        with patch('urllib2.urlopen', Mock(side_effect=ValueError("network status fail"))):
            self.assertFalse(utils.check_network_status(Mock(), 10))