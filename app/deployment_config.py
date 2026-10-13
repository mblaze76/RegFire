"""Explicit HTTP boundary settings. Production mode fails closed without HTTPS."""
from dataclasses import dataclass
from urllib.parse import urlsplit
import os

@dataclass(frozen=True)
class DeploymentConfig:
    origin: str
    host: str
    secure_cookies: bool

    @classmethod
    def load(cls, port, environ=None):
        env = os.environ if environ is None else environ
        mode = env.get('REGFIRE_ENV', 'local')
        if mode not in ('local', 'production'):
            raise ValueError('REGFIRE_ENV must be local or production.')
        if mode == 'local':
            return cls('http://127.0.0.1:'+str(port), '127.0.0.1:'+str(port), False)
        origin = env.get('REGFIRE_PUBLIC_ORIGIN', '')
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
                parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError('Production requires REGFIRE_PUBLIC_ORIGIN as an HTTPS origin without a path.')
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError('Invalid production origin port.') from exc
        return cls(origin, parsed.netloc, True)

    def allows_host(self, host):
        return host == self.host or (not self.secure_cookies and host == self.host.replace('127.0.0.1:', 'localhost:'))

    def allows_origin(self, origin, host):
        return self.allows_host(host) and origin == (self.origin if self.secure_cookies else 'http://'+host)
