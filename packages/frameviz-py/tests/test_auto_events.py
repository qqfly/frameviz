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
