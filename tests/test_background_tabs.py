from collections import deque
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from extraction import BackgroundTabs, ProtocolError, TabClosed


class BrowserSocket:
    """Model the protocol responses a browser emits while replacing a document."""
    def __init__(self, evaluations, *, closed=False):
        self.evaluations = deque(evaluations)
        self.responses = deque()
        self.closed = closed
        self.methods = []

    def send(self, raw):
        message = json.loads(raw)
        method = message['method']
        self.methods.append(method)
        reply = {'type': 'success', 'result': {}}
        if method == 'browsingContext.getTree':
            if self.closed and message['params'].get('root'):
                reply = {'type': 'error', 'error': 'no such frame', 'message': 'Tab is closed'}
            else:
                reply['result'] = {'contexts': [{'context': 'tab'}]}
        elif method == 'network.addIntercept':
            reply['result'] = {'intercept': 'downloads'}
        elif method == 'script.evaluate':
            reply = self.evaluations.popleft()
        self.responses.append(dict(reply, id=message['id']))

    def recv(self):
        return json.dumps(self.responses.popleft())

    def close(self):
        pass


def result(value):
    return {'type': 'success', 'result': {'type': 'success',
        'result': {'type': 'string', 'value': json.dumps(value)}}}


def failure(message, code='unknown error'):
    return {'type': 'error', 'error': code, 'message': message}


class BackgroundTabTests(unittest.TestCase):
    def tabs(self, evaluations, *, closed=False, diagnostics=None):
        socket = BrowserSocket(evaluations, closed=closed)
        driver = SimpleNamespace(capabilities={'webSocketUrl': 'ws://localhost/browser'})
        with patch('extraction.create_connection', return_value=socket):
            tabs = BackgroundTabs(driver, on_diagnostic=(diagnostics.append if diagnostics is not None else lambda message: None))
        self.addCleanup(tabs.close)
        return tabs, socket

    def test_redirect_context_loss_waits_and_then_resolves_the_link(self):
        diagnostics = []
        tabs, _ = self.tabs([
            failure('Cannot find context with specified id'),
            failure('Cannot find context with specified id'),
            result({'verification': True}),
            result({'url': 'https://dl.fuckingfast.co/test'}),
        ], diagnostics=diagnostics)
        self.assertEqual(tabs.poll('tab'), {})
        self.assertEqual(tabs.poll('tab'), {})
        self.assertEqual(len(diagnostics), 1)
        self.assertIn('Cannot find context', diagnostics[0])
        self.assertTrue(tabs.poll('tab')['verification'])
        self.assertEqual(tabs.poll('tab')['url'], 'https://dl.fuckingfast.co/test')

    def test_missing_script_frame_is_retried_while_the_tab_still_exists(self):
        tabs, _ = self.tabs([failure('No script frame', 'no such frame'), result({})])
        self.assertEqual(tabs.poll('tab'), {})
        self.assertEqual(tabs.poll('tab'), {})

    def test_a_closed_tab_is_not_mistaken_for_a_redirect(self):
        tabs, _ = self.tabs([failure('Cannot find context with specified id')], closed=True)
        with self.assertRaises(TabClosed):
            tabs.poll('tab')

    def test_unrelated_protocol_errors_are_reported_with_their_original_details(self):
        tabs, socket = self.tabs([failure('Browser connection is unhealthy', 'unknown error')])
        with self.assertRaises(ProtocolError) as raised:
            tabs.poll('tab')
        self.assertEqual(str(raised.exception), 'Browser connection is unhealthy')
        self.assertEqual(raised.exception.code, 'unknown error')
        self.assertEqual(raised.exception.method, 'script.evaluate')
        self.assertEqual(socket.methods.count('browsingContext.getTree'), 1)
