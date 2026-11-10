"""Public callback lifecycle boundaries, separate from browser pointer checks."""

def test_manual_correlated_wait_runs_application_filter_outside_internal_lock(mock_client):
    client, _ = mock_client
    client.auto_events = False
    client._query_events['q'] = ('query_response', {'request_id': 'q'})

    def matches(data):
        assert client._lock.acquire(blocking=False), 'Application filter ran under the client lock'
        client._lock.release()
        return data['request_id'] == 'q'

    assert client.wait_for_event('query_response', timeout=.1, filter_fn=matches) == {'request_id': 'q'}


def test_dispatch_uses_a_handler_snapshot_when_handlers_change(mock_client):
    client, _ = mock_client
    calls = []

    def first(data):
        calls.append('first')
        client.off_event('example', second)

    def second(data):
        calls.append('second')

    client.on_event('example', first)
    client.on_event('example', second)
    client._event_queue.put(('example', {}))
    client.poll_events()
    assert calls == ['first', 'second']


def test_callback_exception_reports_traceback_and_continues(mock_client, capsys):
    client, _ = mock_client
    seen = []

    def broken(data):
        raise ValueError('Synthetic callback failure')

    client.on_event('example', broken)
    client.on_event('example', lambda data: seen.append(data['n']))
    client._event_queue.put(('example', {'n': 1}))
    client._event_queue.put(('example', {'n': 2}))
    client.poll_events()
    error = capsys.readouterr().err
    assert error.count('Traceback (most recent call last)') == 2
    assert 'in broken' in error and 'ValueError: Synthetic callback failure' in error
    assert seen == [1, 2]


def test_close_inside_handler_stops_remaining_handlers(mock_client):
    client, _ = mock_client
    seen = []
    client.on_event('example', lambda data: client.close())
    client.on_event('example', lambda data: seen.append('after close'))
    client._event_queue.put(('example', {}))
    client.poll_events()
    assert seen == []


def test_manual_event_wait_finishes_when_connection_is_closed(mock_client):
    import threading

    client, _ = mock_client
    client.auto_events = False
    registered = threading.Event()
    results = []
    on_event = client.on_event

    def observe_registration(name, handler):
        on_event(name, handler)
        registered.set()

    client.on_event = observe_registration
    worker = threading.Thread(target=lambda: results.append(client.wait_for_event('never', timeout=3)))
    worker.start()
    try:
        assert registered.wait(1)
        client.close()
        worker.join(timeout=.5)
        assert not worker.is_alive(), 'Explicit close left manual event wait running'
        assert results == [None]
        assert not client._event_handlers.get('never')
    finally:
        worker.join(timeout=4)
