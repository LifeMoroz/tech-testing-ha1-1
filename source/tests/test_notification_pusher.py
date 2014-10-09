import unittest
import mock

import source.notification_pusher as notification_pusher
from gevent import queue as gevent_queue


def russian_woman_and_horse(*args, **kwargs):
    notification_pusher.run = False


class MainLoopTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _config(self):
        config = mock.Mock()
        config.QUEUE_PORT = 42
        config.QUEUE_HOST = 'host'
        config.QUEUE_SPACE = 0
        config.QUEUE_TUBE = 'tube'
        config.QUEUE_TAKE_TIMEOUT = 0
        config.WORKER_POOL_SIZE = 0
        config.SLEEP = 1
        return config

    @mock.patch('source.lib.utils.tarantool_queue.Queue')
    @mock.patch('source.notification_pusher.Pool')
    @mock.patch('source.notification_pusher.gevent_queue.Queue')
    def test_main_loop_stopped(self, m_gevent_queue, m_pool, m_queue):
        notification_pusher.run = False
        notification_pusher.logger = mock.Mock()
        config = self._config()
        notification_pusher.main_loop(config)

        self.assertEqual(m_queue.call_count, 1, "Expected only one call")
        m_pool.assert_called_once_with(config.WORKER_POOL_SIZE)
        self.assertEqual(m_gevent_queue.call_count, 1, "Expected only one call")
        notification_pusher.logger.info.assert_called_with('Stop application loop.')


    @mock.patch('source.notification_pusher.gevent_queue.Queue', mock.Mock())
    @mock.patch('source.lib.utils.tarantool_queue.Queue')
    @mock.patch('source.notification_pusher.Pool')
    def test_main_loop_run(self, m_pool, m_queue):
        notification_pusher.run = True
        workers_count = 5

        m_pool().free_count = mock.Mock(return_value=workers_count)

        m_queue().tube = mock.Mock()
        m_queue().tube.take = mock.Mock(return_value=type('', (), {'task_id': 42}))

        with mock.patch('source.notification_pusher.sleep', mock.Mock(side_effect=russian_woman_and_horse)), \
                mock.patch('source.notification_pusher.done_with_processed_tasks', mock.Mock()):
            notification_pusher.main_loop(self._config())

        self.assertEquals(m_queue().tube().take.call_count, workers_count)
        self.assertEquals(m_pool().add.call_count, workers_count)


class StopHandlerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        notification_pusher.logger = mock.Mock()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('source.notification_pusher.current_thread', mock.Mock())
    def test_stop_handler(self):
        signum = 42
        notification_pusher.stop_handler(signum)
        self.assertEquals(
            notification_pusher.exit_code,
            notification_pusher.SIGNAL_EXIT_CODE_OFFSET + signum
        )


class DoneWithProcessedTasksTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        notification_pusher.logger = mock.Mock()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _m_task_queue(self, m_get_nowait):
        m_task_queue = mock.Mock()
        m_task_queue.qsize = mock.Mock(return_value=1)
        m_task_queue.get_nowait = m_get_nowait
        return m_task_queue

    def test_done_with_processed_tasks_successed(self):
        m_task = mock.Mock()
        m_task.task_method = mock.Mock()

        notification_pusher.done_with_processed_tasks(self._m_task_queue(mock.Mock(return_value=(m_task, 'task_method'))))

        self.assertEqual(m_task.task_method.call_count, 1, "Expected only one call")

    def test_done_with_processed_tasks_db_error(self):
        import tarantool

        m_task = mock.Mock()
        m_task.task_method = mock.Mock(side_effect=tarantool.DatabaseError())

        try:
            notification_pusher.done_with_processed_tasks(self._m_task_queue(mock.Mock(return_value=(m_task,
                                                                                                     'task_method'))))
        except tarantool.DatabaseError:
            self.fail("DatabaseError exception must be caught")

    def test_done_with_processed_tasks_queue_is_empty(self):
        m_task_queue = self._m_task_queue(mock.Mock(side_effect=notification_pusher.gevent_queue.Empty))

        try:
            notification_pusher.done_with_processed_tasks(m_task_queue)
        except gevent_queue.Empty:
            self.fail("gevent_queue.Empty exception must be caught")


class NotificationWorkerCaseTest(unittest.TestCase):
    def setUp(self):
        notification_pusher.logger = mock.Mock()
        self.worker_task = type('', (), {
            'data': {'callback_url': 'url'},
            'task_id': 42,
        })
        self.m_task_queue = mock.Mock()

    @mock.patch('source.notification_pusher.current_thread', mock.Mock())
    @mock.patch('source.notification_pusher.requests', mock.Mock())
    def test_notification_worker_success(self):
        notification_pusher.notification_worker(
            self.worker_task, self.m_task_queue
        )

        self.m_task_queue.put.assert_called_once_with((self.worker_task, 'ack'))

    @mock.patch('source.notification_pusher.current_thread', mock.Mock())
    @mock.patch('source.notification_pusher.requests.post',
                mock.Mock(side_effect=[notification_pusher.requests.RequestException()]))
    def test_notification_worker_request_exception(self):
        notification_pusher.notification_worker(
            self.worker_task, self.m_task_queue
        )

        self.m_task_queue.put.assert_called_once_with((self.worker_task, 'bury'))


class InstallSignalHandlersTestCase(unittest.TestCase):
    def setUp(self):
        notification_pusher.logger = mock.Mock()

    @mock.patch('source.notification_pusher.gevent')
    @mock.patch('source.notification_pusher.stop_handler')
    def test(self, m_handler, m_gevent):
        import signal

        notification_pusher.install_signal_handlers()

        signals = [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]

        for call in m_gevent.method_calls:
            self.assertTrue(call[0] == 'signal' and call[1][0] in signals)


class MainTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        notification_pusher.logger = mock.Mock()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _test_run(self, daemon, pidfile, config):
        args = type('', (), {
            'daemon': daemon,
            'pidfile': pidfile,
            'config': config
        })

        with mock.patch('source.notification_pusher.parse_cmd_args', mock.Mock(return_value=args)), \
                mock.patch('source.notification_pusher.load_config_from_pyfile', mock.Mock()), \
                mock.patch('os.path.realpath', mock.Mock()), \
                mock.patch('os.path.expanduser', mock.Mock()), \
                mock.patch('source.notification_pusher.patch_all', mock.Mock()), \
                mock.patch('source.notification_pusher.dictConfig', mock.Mock()), \
                mock.patch('source.notification_pusher.current_thread', mock.Mock()), \
                mock.patch('source.notification_pusher.install_signal_handlers', mock.Mock()):
            return notification_pusher.main("args")

    def test_return(self):
        pidfile = 'pidfile'
        exit_code = 42

        notification_pusher.run = False
        notification_pusher.exit_code = exit_code

        with mock.patch('source.notification_pusher.daemonize', mock.Mock()) as m_daemon, \
                mock.patch('source.notification_pusher.create_pidfile', mock.Mock()) as m_create:
            exit_code_was = self._test_run(True, pidfile, 'config')

        self.assertEqual(m_daemon.call_count, 1, "Expected only one call")
        m_create.assert_called_once_with(pidfile)
        notification_pusher.logger.info.assert_called_with('Stop application loop in main.')
        self.assertEqual(exit_code_was, exit_code)

    def test_run(self):
        notification_pusher.run = True
        with mock.patch('source.notification_pusher.create_pidfile', mock.Mock()), \
                mock.patch('source.notification_pusher.daemonize', mock.Mock()), \
                mock.patch('source.notification_pusher.main_loop', mock.Mock(side_effect=russian_woman_and_horse)) as m_main_loop:
            self._test_run(False, None, None)
        self.assertEqual(m_main_loop.call_count, 1, "Expected only one call")

    def test_run_sleep(self):
        notification_pusher.run = True
        with mock.patch('source.notification_pusher.create_pidfile', mock.Mock()), \
                mock.patch('source.notification_pusher.daemonize', mock.Mock()), \
                mock.patch('source.notification_pusher.main_loop', mock.Mock(side_effect=Exception)) as m_main_loop, \
                mock.patch('source.notification_pusher.sleep', mock.Mock(side_effect=russian_woman_and_horse)) as m_sleep:
            self._test_run(True, 'pidfile', 'config')

        self.assertEqual(m_main_loop.call_count, 1, "Expected only one call")
        self.assertEqual(m_sleep.call_count, 1, "Expected only one call")