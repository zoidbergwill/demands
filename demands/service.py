import logging
import requests
import time


log = logging.getLogger(__name__)


class Request(object):
    """Request object for http requests/responses."""
    
    def __init__(self, url, method, cookies=None, data=None, headers=None,
                 params=None, verify=False):
        self.url = url or {}
        self.method = method or {}
        self.cookies = cookies or {}
        self.data = data or {}
        self.headers = headers or {}
        self.params = params or {}
        self.verify = verify
        self.auth = None

    def _compose_request_arguments(self):
        """Compose arguments as expected by the requests library."""
        arguments = {}
        arguments['params'] = self.params
        arguments['data'] = self.data
        arguments['cookies'] = self.cookies
        arguments['headers'] = self.headers
        arguments['auth'] = self.auth
        arguments['verify'] = self.verify
        return arguments

    def authenticate(self, username, password):
        """Enable http authentication with the provided username and password"""
        log.debug('Authentication via HTTP auth as "%s"', username)
        self.auth = (username, password)

    def send(self):
        """Execute the request, and return the response"""
        method = self.method.lower()
        request_arguments = self._compose_request_arguments()
        start_time = time.time()
        response = getattr(requests, method)(self.url, **request_arguments)
        log.debug('%s HTTP [%s] call to "%s" %.2fms', response.status_code, self.method, self.url,
                  (time.time() - start_time) * 1000)
        log.debug('HTTP request args: %s', request_arguments)
        return response


class HTTPServiceError(Exception):
    def __init__(self, code, details):
        self.code = code
        super(Exception, self).__init__(
            'code: %s, details: %s' % (code, details)
        )


class HTTPService(object):
    """
    Provides an interface which allows arbitrary methods to be defined and
    called on a remote http service.
    """
    def __init__(self, config):
        self.config = config

    def pre_send(self, request, **params):
        """
        Override to modify request object to be called just before sending
        the request
        """
        if 'username' in self.config:
            request.authenticate(
                self.config['username'], self.config['password'])

        if 'client_name' in self.config:
            request.headers['User-Agent'] = '%s %s - %s' % (
                self.config['client_name'],
                self.config.get('client_version', 'x.y.z'),
                self.config.get('app_name', 'unknown'),
            )

    def post_send(self, request, response, **params):
        """Override to modify response object returned by call made by request object."""
        response.is_ok = response.status_code < 300
        if (not response.is_ok and
                not response.status_code in params.get('expected_response_codes', [])):
            log.error('Unexpected response from %s: url: %s, code: %s, details: %s',
                self.__class__.__name__, response.url, response.status_code, response.content)

            raise HTTPServiceError(response.status_code, response.content)

    def get(self, path, **kwargs):
        return self._make_call('GET', **kwargs)

    def post(self, path, **kwargs):
        return self._make_call('POST', path, **kwargs)

    def put(self, path, **kwargs):
        return self._make_call('PUT', path, **kwargs)

    def delete(self, path, **kwargs):
        return self._make_call('DELETE', path, **kwargs)

    def _make_call(self, method, path, **kwargs):
        """
        Call the service method defined by the passed path and http method.
        Additional arguments include cookies, headers, body, and data values.
        """
        base = self.config.get('url')
        url = '/'.join([base.rstrip('/'), path.lstrip('/')])

        # Verify precedence 
        # HTTP (False) < HTTPS (True) < HTTPService config < call argument
        verify = True if url.startswith('https') else False
        verify = self.config.get('verify_ssl', verify)
        verify = kwargs.pop('verify', verify)

        request = Request(url, method, verify=verify, **kwargs)

        self.pre_send(request, **kwargs)
        response = request.send()
        self.post_send(request, response, **kwargs)
        return response
