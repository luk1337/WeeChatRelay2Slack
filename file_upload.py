import http
from enum import Enum

import requests

from config import Config


class FileUploadProvider(Enum):
    NONE = 0
    GCF_UPLOAD = 1
    LOLISAFE = 2
    POMF = 3

    @staticmethod
    def from_str(string: str):
        try:
            return FileUploadProvider[string]
        except KeyError:
            return FileUploadProvider.NONE


class FileUpload:
    @staticmethod
    def _handle_none(buffer: str):
        return False, 'Uploading files is not enabled.'

    @staticmethod
    def _handle_gcf_upload(filename: str, buffer: str, mime: str):
        try:
            response = requests.post('{}/put'.format(Config.FileUpload.GcfUpload.URL),
                                     files={'file': (filename, buffer, mime)},
                                     headers={'X-Api-Key': Config.FileUpload.GcfUpload.ApiKey})
        except Exception as e:
            return False, 'Failed to upload file ({})'.format(str(e))

        if response.status_code != http.HTTPStatus.OK:
            return False, 'Failed to upload file (status code: {})'.format(response.status_code)

        return True, response.url

    @staticmethod
    def _handle_lolisafe(filename: str, buffer: str, mime: str):
        try:
            request = requests.post('{}/api/upload'.format(Config.FileUpload.Lolisafe.URL),
                                    files={'files[]': (filename, buffer, mime)},
                                    headers={'token': Config.FileUpload.Lolisafe.Token})
        except Exception as e:
            return False, 'Failed to upload file ({})'.format(str(e))

        try:
            response = request.json()
        except ValueError as e:
            return False, 'Failed to upload file ({})'.format(str(e))

        if request.status_code != http.HTTPStatus.OK:
            return False, 'Failed to upload file (status code: {})'.format(response['description'])

        return True, response['files'][0]['url']

    @staticmethod
    def _handle_pomf(filename: str, buffer: str, mime: str):
        try:
            request = requests.post('{}/upload.php'.format(Config.FileUpload.Pomf.URL),
                                    files={'files[]': (filename, buffer, mime)},
                                    headers={'token': Config.FileUpload.Pomf.Token})
        except Exception as e:
            return False, 'Failed to upload file ({})'.format(str(e))

        try:
            response = request.json()
        except ValueError as e:
            return False, 'Failed to upload file ({})'.format(str(e))

        if request.status_code != http.HTTPStatus.OK:
            return False, 'Failed to upload file (status code: {})'.format(response['description'])

        return True, response['files'][0]['url']

    @staticmethod
    def upload(filename: str, buffer: str, mime: str):
        providers = {
            FileUploadProvider.NONE: FileUpload._handle_none,
            FileUploadProvider.GCF_UPLOAD: FileUpload._handle_gcf_upload,
            FileUploadProvider.LOLISAFE: FileUpload._handle_lolisafe,
            FileUploadProvider.POMF: FileUpload._handle_pomf,
        }

        return providers[FileUploadProvider.from_str(Config.FileUpload.Provider)](filename, buffer, mime)
