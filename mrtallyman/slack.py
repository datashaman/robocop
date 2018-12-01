import hashlib
import hmac
import os
import time

from slackclient import SlackClient
from .decorators import memoize

handlers = {}

def on(name):
    def decorator_on(func):
        global handlers

        if name not in handlers:
            handlers[name] = []
        found = False
        for handler in handlers[name]:
            if (handler.__module__, handler.__name__) == (func.__module__, func.__name__):
                found = True
                break
        if not found:
            handlers[name].append(func)
        return func
    return decorator_on

@memoize
def get_client(team_id):
    from .db import get_bot_access_token
    token = get_bot_access_token(team_id)
    return SlackClient(token)

def get_bot_by_token(token):
    client = SlackClient(token)
    return client.api_call('auth.test')

def post_message(team_id, text, channel):
    get_client(team_id).api_call(
        'chat.postMessage',
        channel=channel,
        text=text
    )

def handle_event(payload):
    event_type = payload['event']['type']

    if event_type in handlers:
        for func in handlers[event_type]:
            func(payload)
        return True
    return False

def generate_signature(timestamp, slack_signing_secret, data):
    key = bytes(slack_signing_secret, 'utf-8')
    msg = ('v0:' + timestamp + ':' + data).encode('utf-8')
    return 'v0=' + hmac.new(key, msg, hashlib.sha256).hexdigest()

def valid_request(app, request):
    timestamp = request.headers['X-Slack-Request-Timestamp']
    if abs(time.time() - float(timestamp)) > 60 * 5:
        return False
    data = request.get_data().decode()
    signature = generate_signature(timestamp, os.environ['SLACK_SIGNING_SECRET'], data)
    return hmac.compare_digest(signature, request.headers['X-Slack-Signature'])

def handle_request(app, request):
    if valid_request(app, request):
        payload = request.get_json()

        if payload['type'] == 'event_callback':
            return handle_event(payload)
        elif payload['type'] == 'url_verification':
            return payload['challenge']
    return False
