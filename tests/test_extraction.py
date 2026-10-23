import unittest

from extraction import TabClosed, TabQueue


class Clock:
    now = 0

    def __call__(self):
        return self.now


class Stop:
    def __init__(self, clock):
        self.clock = clock
        self.stopped = False

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, seconds):
        self.clock.now += 1


class Tabs:
    def __init__(self, delays=None, closed=None):
        self.active = {}
        self.peak = 0
        self.closed = []
        self.delays = delays or {}
        self.user_closed = closed

    def open(self, url):
        self.active[url] = 0
        self.peak = max(self.peak, len(self.active))
        return url

    def poll(self, context):
        if context == self.user_closed:
            raise TabClosed('closed')
        self.active[context] += 1
        if self.active[context] >= self.delays.get(context, 2):
            return {'url': 'https://dl.fuckingfast.co/' + context}
        return {}

    def close_tab(self, context):
        self.closed.append(context)
        self.active.pop(context, None)


class QueueTests(unittest.TestCase):
    def run_queue(self, urls, limit, tabs=None, timeout=120):
        clock = Clock()
        stop = Stop(clock)
        tabs = tabs or Tabs()
        jobs = TabQueue(tabs, timeout=timeout, interval=0, clock=clock).run(urls, limit, stop)
        return jobs, tabs

    def test_bound_is_respected_and_results_keep_input_order(self):
        tabs = Tabs(delays={'one': 4, 'two': 1, 'three': 2})
        jobs, tabs = self.run_queue(['one', 'two', 'three', 'four', 'five'], 3, tabs)
        self.assertEqual(tabs.peak, 3)
        self.assertEqual([job.url for job in jobs], ['one', 'two', 'three', 'four', 'five'])
        self.assertTrue(all(job.state == 'Complete' for job in jobs))
        self.assertFalse(tabs.active)
        self.assertEqual(len(tabs.closed), 5)

    def test_limit_one_processes_sequentially(self):
        jobs, tabs = self.run_queue(['one', 'two', 'three'], 1)
        self.assertEqual(tabs.peak, 1)
        self.assertTrue(all(job.direct_url for job in jobs))

    def test_closed_tab_does_not_cancel_other_files(self):
        jobs, tabs = self.run_queue(['closed', 'good'], 2, Tabs(closed='closed'))
        self.assertEqual([job.state for job in jobs], ['Failed', 'Complete'])
        self.assertFalse(tabs.active)

    def test_timeout_closes_only_the_affected_tab(self):
        jobs, tabs = self.run_queue(['slow', 'good'], 2, Tabs(delays={'slow': 1000}), timeout=2)
        self.assertEqual([job.state for job in jobs], ['Timed out', 'Complete'])
        self.assertFalse(tabs.active)

    def test_read_errors_keep_the_cause_and_do_not_cancel_other_files(self):
        class BrokenTabs(Tabs):
            def poll(self, context):
                if context == 'broken':
                    raise RuntimeError('Browser connection dropped')
                return super().poll(context)
        clock = Clock()
        errors = []
        jobs = TabQueue(BrokenTabs(), interval=0, clock=clock).run(
            ['broken', 'good'], 2, Stop(clock),
            on_error=lambda job, error: errors.append((job.index, str(error))))
        self.assertEqual([job.state for job in jobs], ['Failed', 'Complete'])
        self.assertIn('Browser connection dropped', jobs[0].detail)
        self.assertEqual(errors, [(0, 'Browser connection dropped')])

    def test_stop_preserves_completed_links_and_cancels_the_rest(self):
        clock = Clock()
        stop = Stop(clock)
        tabs = Tabs(delays={'fast': 1, 'slow': 1000})
        def progress(done, total, active):
            if done:
                stop.set()
        jobs = TabQueue(tabs, interval=0, clock=clock).run(['fast', 'slow', 'queued'], 2, stop, on_progress=progress)
        self.assertEqual([job.state for job in jobs], ['Complete', 'Cancelled', 'Cancelled'])
        self.assertTrue(jobs[0].direct_url)
        self.assertFalse(tabs.active)

    def test_invalid_limits_are_rejected_before_opening_tabs(self):
        for limit in (0, 13):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.run_queue(['one'], limit)
