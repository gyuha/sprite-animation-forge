"""Shared scripted-transport helpers for the sg_* tests (fake clock, scripted xAI answers)."""

import json

OK_DONE = json.dumps({"status": "done", "video": {"url": "https://cdn.fake/v.mp4"}}).encode()
ACCEPTED = json.dumps({"request_id": "req-1"}).encode()
LONG_KEY = "xai-" + "A1b2C3d4" * 6


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Script:
    """A transport answering from a list per kind of call; records (method, url, timeout)."""

    def __init__(self, clock, polls=(), downloads=(), post=(200, ACCEPTED), step=0.0):
        self.clock, self.polls, self.downloads, self.post, self.step = clock, list(polls), list(downloads), post, step
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, timeout))
        self.clock.now += self.step
        if method == "POST":
            return self.post
        queue = self.downloads if url.startswith("https://cdn") else self.polls
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item
