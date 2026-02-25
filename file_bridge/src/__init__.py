"""file_bridge — SCP ファイル転送パッケージ。

Jupyter Notebook からは以下のようにインポートして使用します::

    from src.client import SCPClient

    client = SCPClient(host="192.168.1.100", user="admin", password="secret")
    client.download(remote="/data/*.csv", local="./downloads/")
"""

from .client import SCPClient

__all__ = ["SCPClient"]
