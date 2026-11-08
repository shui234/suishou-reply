"""Windows Credential Manager storage, with no plaintext fallback."""

import ctypes
from ctypes import wintypes
import sys


class CredentialError(RuntimeError):
    """Safe, user-visible credential storage error."""


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ('Flags', wintypes.DWORD), ('Type', wintypes.DWORD),
        ('TargetName', wintypes.LPWSTR), ('Comment', wintypes.LPWSTR),
        ('LastWritten', wintypes.FILETIME), ('CredentialBlobSize', wintypes.DWORD),
        ('CredentialBlob', ctypes.POINTER(wintypes.BYTE)), ('Persist', wintypes.DWORD),
        ('AttributeCount', wintypes.DWORD), ('Attributes', ctypes.c_void_p),
        ('TargetAlias', wintypes.LPWSTR), ('UserName', wintypes.LPWSTR),
    ]


def _load_api():
    if sys.platform != 'win32':
        raise OSError('Windows Credential Manager required')
    api = ctypes.WinDLL('Advapi32.dll', use_last_error=True)
    api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             ctypes.POINTER(ctypes.POINTER(_CREDENTIALW))]
    api.CredReadW.restype = wintypes.BOOL
    api.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIALW), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    api.CredDeleteW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    api.CredFree.restype = None
    return api


class CredentialStore:
    def __init__(self, target: str = 'SuishouReply/DeepSeekAPI'):
        if not isinstance(target, str) or not target or '\x00' in target:
            raise CredentialError('凭据名称无效。')
        self.target = target

    def get(self) -> str | None:
        try:
            api = _load_api()
            pointer = ctypes.POINTER(_CREDENTIALW)()
            if not api.CredReadW(self.target, 1, 0, ctypes.byref(pointer)):
                if ctypes.get_last_error() == 1168:  # ERROR_NOT_FOUND
                    return None
                raise OSError('CredReadW failed')
            try:
                credential = pointer.contents
                if not 0 < credential.CredentialBlobSize <= 2560:
                    raise ValueError('Invalid credential length')
                return ctypes.string_at(credential.CredentialBlob,
                                        credential.CredentialBlobSize).decode('utf-8')
            finally:
                api.CredFree(pointer)
        except (OSError, ValueError, UnicodeError):
            raise CredentialError('无法读取 Windows 凭据管理器，请重新保存 API 密钥。') from None

    def set(self, key: str) -> None:
        if (not isinstance(key, str) or not key.strip() or not key.isascii()
                or any(c in key for c in '\r\n\x00')
                or len(key.encode('utf-8')) > 2560):
            raise CredentialError('API 密钥格式无效，请检查后重试。')
        blob = ctypes.create_string_buffer(key.strip().encode('utf-8'))
        try:
            api = _load_api()
            credential = _CREDENTIALW()
            credential.Type = 1  # CRED_TYPE_GENERIC
            credential.TargetName = self.target
            credential.CredentialBlobSize = len(blob.raw) - 1
            credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(wintypes.BYTE))
            credential.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE, current Windows user
            credential.UserName = 'DeepSeek API'
            if not api.CredWriteW(ctypes.byref(credential), 0):
                raise OSError('CredWriteW failed')
        except OSError:
            raise CredentialError('无法保存到 Windows 凭据管理器，密钥未保存。') from None
        finally:
            ctypes.memset(blob, 0, len(blob))

    def delete(self) -> None:
        try:
            api = _load_api()
            if not api.CredDeleteW(self.target, 1, 0) and ctypes.get_last_error() != 1168:
                raise OSError('CredDeleteW failed')
        except OSError:
            raise CredentialError('无法删除 Windows 凭据管理器中的密钥，请稍后重试。') from None
