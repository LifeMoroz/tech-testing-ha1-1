import unittest
import mock
from source.lib.utils import Config
from source import redirect_checker


def stop_main_loop(*argv):
    redirect_checker.run = False


class RedirectCheckerTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _redirect_checker_main(self, args):
        config = Config()
        config.LOGGING = mock.Mock()
        config.EXIT_CODE = 0
        with mock.patch('source.redirect_checker.parse_cmd_args', mock.MagicMock(return_value=args)),\
                mock.patch('source.redirect_checker.daemonize', mock.Mock()) as daemonize,\
                mock.patch('source.redirect_checker.dictConfig', mock.Mock()),\
                mock.patch('source.redirect_checker.main_loop', mock.Mock()),\
                mock.patch('source.redirect_checker.load_config_from_pyfile', mock.Mock(return_value=config)),\
                mock.patch('os.path.realpath', mock.Mock()),\
                mock.patch('os.path.expanduser', mock.Mock()),\
                mock.patch('source.redirect_checker.sys.exit', mock.Mock(side_effect=None)),\
                mock.patch('source.redirect_checker.create_pidfile', mock.Mock()) as create_pid:
            exit_code = redirect_checker.main(args)
            return exit_code == config.EXIT_CODE, daemonize.called, create_pid.called

    def test_main_daemon_pidfile(self):
        """
        Test correct work
        """
        args = mock.MagicMock()
        args.daemon = True
        args.pidfile = True
        self.assertEquals((True, True, True), self._redirect_checker_main(args))

    def test_main_no_daemon_no_pidfile(self):
        """
        Test correct work without deamon or pidfile
        """
        args = mock.MagicMock()
        args.daemon = False
        args.pidfile = False
        self.assertEquals((True, False, False), self._redirect_checker_main(args))

    def test_main_loop_dfs(self):
        """
        try to go deeper
        """
        pid = 42
        config = Config()
        config.SLEEP = 1
        config.CHECK_URL = 'url'
        config.HTTP_TIMEOUT = 1
        config.WORKER_POOL_SIZE = 50
        mock_spawn_workers = mock.Mock()
        mock_check_network_status = mock.Mock(return_value=True)
        children = [mock.Mock()]
        count = config.WORKER_POOL_SIZE - len(children)
        mock_sleep = mock.Mock(side_effect=stop_main_loop)
        with mock.patch('source.redirect_checker.check_network_status', mock_check_network_status),\
                 mock.patch('os.getpid', mock.Mock(return_value=pid)),\
                 mock.patch('source.redirect_checker.spawn_workers', mock_spawn_workers),\
                 mock.patch('source.redirect_checker.active_children', mock.Mock(return_value=children)),\
                 mock.patch('source.redirect_checker.sleep', mock_sleep):
            redirect_checker.main_loop(config)
        self.assert_(mock_spawn_workers.call_args[1]['num'] == count)
        self.assert_(mock_spawn_workers.call_args[1]['parent_pid'] == pid)
        redirect_checker.run = True

    def test_main_loop_no_workers(self):
        pid = 42
        config = Config()
        config.SLEEP = 8
        config.CHECK_URL = 'url'
        config.HTTP_TIMEOUT = 1
        config.WORKER_POOL_SIZE = 2
        active_children = [mock.Mock() for _ in range(6)]
        mock_spawn_workers = mock.Mock()
        mock_check_network_status = mock.Mock(return_value=True)
        mock_sleep = mock.Mock(side_effect=stop_main_loop)
        with mock.patch('source.redirect_checker.check_network_status', mock_check_network_status),\
                 mock.patch('os.getpid', mock.Mock(return_value=pid)),\
                 mock.patch('source.redirect_checker.spawn_workers', mock_spawn_workers),\
                 mock.patch('source.redirect_checker.active_children', mock.Mock(return_value=active_children)),\
                 mock.patch('source.redirect_checker.sleep', mock_sleep):
            redirect_checker.main_loop(config)
        self.assertEqual(mock_spawn_workers.call_count, 0)
        mock_sleep.assert_called_once_with(config.SLEEP)
        redirect_checker.run = True

    def test_main_loop_network_status_is_not_fine(self):
        pid = 42
        config = Config()
        config.SLEEP = 8
        config.CHECK_URL = 'url'
        config.HTTP_TIMEOUT = 1
        config.WORKER_POOL_SIZE = 2
        mock_spawn_workers = mock.Mock()
        mock_check_network_status = mock.Mock(return_value=False)
        test_active_children = mock.Mock()
        mock_sleep = mock.Mock(side_effect=stop_main_loop)
        with mock.patch('source.redirect_checker.check_network_status', mock_check_network_status),\
                mock.patch('os.getpid', mock.Mock(return_value=pid)),\
                mock.patch('source.redirect_checker.active_children', mock.Mock(return_value=[test_active_children])),\
                mock.patch('source.redirect_checker.sleep', mock_sleep):
            redirect_checker.main_loop(config)
        self.assertEqual(mock_spawn_workers.call_count, 0)
        self.assertEqual(test_active_children.terminate.call_count, 1, "Expected only one call")
        mock_sleep.assert_called_once_with(config.SLEEP)
        redirect_checker.run = True