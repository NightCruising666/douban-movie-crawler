import unittest
from unittest import mock

import requests

from douban_crawler.src import crawler


class CrawlerTests(unittest.TestCase):
    @mock.patch.object(crawler.time, "sleep")
    @mock.patch.object(crawler.requests, "get")
    def test_transport_retry_is_audited_even_if_later_attempt_succeeds(self, get, sleep):
        response = mock.Mock(status_code=200)
        get.side_effect = [requests.exceptions.Timeout("slow"), response]
        reasons = []

        actual = crawler.safe_get("https://example.test", failure_audit=reasons.append)

        self.assertIs(actual, response)
        self.assertEqual(reasons, ["请求超时"])
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(2)


if __name__ == "__main__":
    unittest.main()
