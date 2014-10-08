import unittest
import mock

import source.notification_pusher as notification_pusher



class MainLoopTestCase(unittest.TestCase):
    def setUp(self):
        notification_pusher.logger = mock.Mock()
        self.logger = notification_pusher.logger

        self.config = mock.Mock()
        self.config.QUEUE_PORT = 42
        self.config.QUEUE_HOST = 'host'
        self.config.QUEUE_SPACE = 0
        self.config.QUEUE_TUBE = 'tube'
        self.config.QUEUE_TAKE_TIMEOUT = 0
        self.config.WORKER_POOL_SIZE = 0
        self.config.SLEEP = 1


    @mock.patch('source.notification_pusher.tarantool_queue.Queue')
    @mock.patch('source.notification_pusher.Pool')
    @mock.patch('source.notification_pusher.gevent_queue.Queue')
    def test_main_loop_stopped(self, m_gevent_queue, m_pool, m_queue):
        notification_pusher.run_application = False

        notification_pusher.main_loop(self.config)

        m_queue.assert_called_once()
        m_pool.assert_called_once_with(self.config.WORKER_POOL_SIZE)
        m_gevent_queue.assert_called_once()
        self.logger.info.assert_called_with('Stop application loop.')


    @mock.patch('source.lib.utils.tarantool_queue.Queue')
    @mock.patch('source.notification_pusher.Pool')
    @mock.patch('source.notification_pusher.gevent_queue.Queue')
    def test_main_loop_run(self, m_gevent_queue, m_pool, m_queue):
        notification_pusher.run_application = True
        free_workers_count = 5

        m_pool().free_count = mock.Mock(return_value=free_workers_count)

        class WorkerTask:
            def __init__(self, task_id):
                self.task_id = task_id

        m_queue().tube = mock.Mock()
        m_queue().tube.take = mock.Mock(return_value=WorkerTask(task_id=42))

        def stop_application(*args, **kwargs):
            notification_pusher.run_application = False

        with mock.patch('source.notification_pusher.sleep', mock.Mock(side_effect=stop_application)):
            with mock.patch('source.notification_pusher.done_with_processed_tasks', mock.Mock()):
                notification_pusher.main_loop(self.config)

        self.assertEquals(m_queue().tube().take.call_count, free_workers_count)
        self.assertEquals(m_pool().add.call_count, free_workers_count)


class StopHandlerTestCase(unittest.TestCase):
    def setUp(self):
        self.offset = 24

        notification_pusher.logger = mock.Mock()
        notification_pusher.SIGNAL_EXIT_CODE_OFFSET = self.offset

    @mock.patch('source.notification_pusher.current_thread', mock.Mock())
    def test_stop_handler(self):
        signum = 42

        notification_pusher.stop_handler(signum)

        self.assertEquals(
            notification_pusher.exit_code,
            self.offset + signum
        )


class DoneWithProcessedTasks(unittest.TestCase):
    def setUp(self):
        notification_pusher.logger = mock.Mock()


    def test_task_successed(self):
        m_task = mock.Mock()
        m_task.task_method = mock.Mock()

        m_task_queue = mock.Mock()
        m_task_queue.qsize = mock.Mock(return_value=1)
        m_task_queue.get_nowait = mock.Mock(
            return_value=(m_task, 'task_method')
        )

        notification_pusher.done_with_processed_tasks(m_task_queue)

        m_task.task.assert_called_once()

    def test_task_db_error(self):
        import tarantool

        m_task = mock.Mock()
        m_task.task_method = mock.Mock(side_effect=tarantool.DatabaseError())

        m_task_queue = mock.Mock()
        m_task_queue.qsize = mock.Mock(return_value=1)
        m_task_queue.get_nowait = mock.Mock(
            return_value=(m_task, 'task_method')
        )

        try:
            notification_pusher.done_with_processed_tasks(m_task_queue)
        except tarantool.DatabaseError:
            self.fail()

    def test_queue_is_empty(self):
        m_task_queue = mock.Mock()
        m_task_queue.qsize = mock.Mock(return_value=1)
        m_task_queue.get_nowait = mock.Mock(
            side_effect=[notification_pusher.gevent_queue.Empty()]
        )

        try:
            notification_pusher.done_with_processed_tasks(m_task_queue)
        except gevent_queue.Empty:
            self.fail()


class NotificationWorkeCaseTest(unittest.TestCase):
    def setUp(self):
        notification_pusher.logger = mock.Mock()

        class WorkerTask():
            def __init__(self):
                self.data = {
                    'callback_url': 'url'
                }
                self.task_id = 42

        self.worker_task = WorkerTask()

    @mock.patch('source.notification_pusher.current_thread', mock.Mock())
    @mock.patch('source.notification_pusher.requests', mock.Mock())
    def test_success(self):
        m_task_queue = mock.Mock()

        notification_pusher.notification_worker(
            self.worker_task, m_task_queue
        )

        m_task_queue.put.assert_called_once_with((self.worker_task, 'ack'))

    @mock.patch('source.notification_pusher.current_thread', mock.Mock())
    @mock.patch('source.notification_pusher.requests.post',
                mock.Mock(side_effect=[notification_pusher.requests.RequestException()]))
    def test_request_exception(self):
        m_task_queue = mock.Mock()

        notification_pusher.notification_worker(
            self.worker_task, m_task_queue
        )

        m_task_queue.put.assert_called_once_with((self.worker_task, 'bury'))


class InstallSignalHandlersTestCase(unittest.TestCase):
    def setUp(self):
        notification_pusher.logger = mock.Mock()

    @mock.patch('source.notification_pusher.gevent')
    @mock.patch('source.notification_pusher.stop_handler')
    def test(self, m_handler, m_gevent):
        import signal

        notification_pusher.install_signal_handlers()

        signals = [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]

        signal_set = {}
        for s in signals:
            signal_set[s] = False

        for c in m_gevent.method_calls:
            if (c[0] == 'signal' and c[1][0] in signals):
                signal_set[c[1][0]] = True

        # TODO: lambda: [if ]
        def signal_is_set(signal_set_list):
            if False in signal_set_list.values():
                return False
            return True

        self.assertTrue(signal_is_set(signal_set))


class MainTestCase(unittest.TestCase):
    def setUp(self):
        notification_pusher.logger = mock.Mock()
        self.logger = notification_pusher.logger


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

        notification_pusher.run_application = False
        notification_pusher.exit_code = exit_code

        with mock.patch('source.notification_pusher.daemonize', mock.Mock()) as m_daemon, \
                mock.patch('source.notification_pusher.create_pidfile', mock.Mock()) as m_create:
            exit_code_was = self._test_run(True, pidfile, 'config')

        m_daemon.assert_called_once()
        m_create.assert_called_once_with(pidfile)  # ZAEBALO
        #m_create.assert_called_once()
        self.logger.info.assert_called_with('Stop application loop in main.')
        self.assertEqual(exit_code_was, exit_code)

    def test_run(self):
        def stop_application(*args, **kwargs):
            notification_pusher.run_application = False

        with mock.patch('source.notification_pusher.create_pidfile', mock.Mock()), \
                mock.patch('source.notification_pusher.daemonize', mock.Mock()), \
                mock.patch('source.notification_pusher.main_loop', mock.Mock(side_effect=stop_application)) as m_main_loop:
            self._test_run(False, None, None)

        m_main_loop.assert_called_once()

    def test_run_sleep(self):
        def stop_application(*args, **kwargs):
            notification_pusher.run_application = False

        with mock.patch('source.notification_pusher.create_pidfile', mock.Mock()), \
             mock.patch('source.notification_pusher.daemonize', mock.Mock()), \
                mock.patch('source.notification_pusher.main_loop', mock.Mock(side_effect=Exception())) as m_main_loop, \
                mock.patch('source.notification_pusher.sleep', mock.Mock(side_effect=stop_application)) as m_sleep:
            self._test_run(True, 'pidfile', 'config')

        m_main_loop.assert_called_once()
        m_sleep.assert_called_once()