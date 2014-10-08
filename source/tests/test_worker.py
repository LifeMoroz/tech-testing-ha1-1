# coding=utf-8
__author__ = 'Ruslan'
from tarantool import DatabaseError
import unittest
import mock

from source.lib import worker


class GetRedirectHistoryFromTaskTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _get_redirect_history(self, task, data_modified, m_return, useragent):
        with mock.patch('source.lib.worker.get_redirect_history', mock.Mock(return_value=m_return)):
            self.assertEquals((useragent, data_modified), (worker.get_redirect_history_from_task(task, 1)))

    def test_get_redirect_history_from_task_error_recheck_false(self):
        """
        history_types with 'ERROR'
        recheck False
        """
        m_return = (['ERROR'], [], [])
        task = mock.Mock()
        task.data = {'url': 'http://example.net', 'recheck': False, 'url_id': 'this is id', 'suspicious': 'suspicious'}
        data_modified = task.data.copy()
        data_modified['recheck'] = True
        self._get_redirect_history(task, data_modified, m_return, True)

    def test_get_redirect_history_from_task_error_recheck_true(self):
        """
        history_types with 'ERROR'
        recheck True
        """
        m_return = [['ERROR'], [], []]
        task = mock.Mock()
        task.data = {'url': 'http://example.net', 'recheck': True, 'url_id': 'this is id'}
        data_modified = {'url_id': task.data['url_id'], 'result': m_return, 'check_type': 'normal'}
        self._get_redirect_history(task, data_modified, m_return, False)

    def test_get_redirect_history_from_task_with_suspicious(self):
        """
        suspicious = suspicious
        """
        m_return = [[], [], []]
        task = mock.Mock()
        task.data = {'url': 'http://example.net', 'recheck': False, 'url_id': 'this is id', 'suspicious': 'suspicious'}
        data_modified = {'url_id': task.data['url_id'], 'result': m_return,
                         'check_type': 'normal', 'suspicious': task.data['suspicious']}
        self._get_redirect_history(task, data_modified, m_return, False)


class WorkerTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _worker(self, tube_side, exists_return, get_redirect_history_from_task_return):
        parent_pid = 33
        config = mock.MagicMock()
        with mock.patch('source.lib.worker.get_tube', mock.Mock(side_effect=tube_side)), \
                mock.patch('os.path.exists', mock.Mock(side_effect=exists_return)),\
                mock.patch('source.lib.worker.get_redirect_history_from_task',
                           mock.Mock(return_value=get_redirect_history_from_task_return)) \
                as get_redirect_history_from_task,\
                mock.patch('source.lib.worker.logger', mock.Mock()) as logger:

            worker.worker(config, parent_pid)

        # Потенциально сюда можно складывать все необходимые к проверке mock'и
        return {'get_redirect_history_from_task': get_redirect_history_from_task,
                'logger': logger}

    def test_worker_parent_is_dead(self):
        """
        parent is dead
        path_exists is false
        """
        tube = mock.MagicMock()
        input_tube = mock.MagicMock()
        output_tube = mock.MagicMock()
        exists_side_effect = [False]
        mocks = self._worker([input_tube, output_tube], exists_side_effect, None)
        self.assertFalse(input_tube.called)

    def test_worker_task_is_none(self):
        """
        task is none
        """
        tube = mock.MagicMock()
        input_tube_take = None
        tube.take = mock.Mock(return_value=input_tube_take)
        mocks = self._worker([tube, tube], [True, False], mock.Mock())
        self.assertFalse(mocks['get_redirect_history_from_task'].called)

    def test_worker_result_is_none(self):
        """
        result is None.
        """
        tube = mock.MagicMock()
        get_redirect_history_from_task_return = None
        input_tube = mock.MagicMock()
        output_tube = mock.MagicMock()
        mocks = self._worker([input_tube, output_tube], [True, False], get_redirect_history_from_task_return)
        self.assertFalse(output_tube.called or input_tube.called)

    def test_worker_result_useragent(self):
        """
        useragent isnt none
        """
        tube = mock.MagicMock()
        input_tube = mock.MagicMock()
        output_tube = mock.MagicMock()
        mocks = self._worker([input_tube, output_tube], (True, False), ['useragent', 'data'])
        self.assertFalse(output_tube.put.called)

    def test_worker_result_not_useragent(self):
        """
        useragent is None
        """
        tube = mock.MagicMock()
        input_tube = mock.MagicMock()
        output_tube = mock.MagicMock()
        mocks = self._worker([input_tube, output_tube], (True, False), [None, 'data'])
        self.assertFalse(input_tube.put.called)

    def test_worker_not_result_database_error(self):
        """
        Raise exception
        """

        tube = mock.MagicMock()
        task = mock.MagicMock()
        tube.take = mock.Mock(return_value=task)
        task.ack = mock.Mock(side_effect=DatabaseError)
        mocks = self._worker([tube, tube], (True, False), None)
        self.assertTrue(mocks['logger'].exception.called)