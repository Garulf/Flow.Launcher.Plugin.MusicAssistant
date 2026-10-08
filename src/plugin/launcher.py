from typing import Optional

from pyflowlauncher import FlowLauncherV2

KEEP_OPEN = {"hide": False}


class MALauncher(FlowLauncherV2):
    """FlowLauncherV2 with three gaps in pyflowlauncher 1.2.1 filled in.

    * A python_v2 host ignores ``DontHideAfterAction`` and hides the window
      unless the action replies ``{"hide": false}``, but pyflowlauncher always
      replies ``{"hide": true}``. Methods return ``KEEP_OPEN`` to stay open.
    * Query handlers only receive ``Query.search``. The action keyword the
      user typed is kept so ``change_query`` can rebuild the full query.
    * ``initialize`` carries the plugin's settings directory, which
      pyflowlauncher answers without exposing.
    """

    def __init__(self) -> None:
        super().__init__()
        self.action_keyword = ""
        self.settings_dir: Optional[str] = None
        messages = self._client.messages

        async def observed_messages():
            async for request in messages():
                self._observe(request)
                yield request

        self._client.messages = observed_messages

    def _observe(self, request: dict) -> None:
        params = request.get("params") or []
        if not params or not isinstance(params[0], dict):
            return
        if request.get("method") == "query":
            self.action_keyword = params[0].get("actionKeyword") or ""
        elif request.get("method") == "initialize":
            metadata = params[0].get("currentPluginMetadata") or {}
            self.settings_dir = metadata.get("pluginSettingsDirectoryPath") or None

    def _send_response(self, request_id, method, result):
        if result == KEEP_OPEN:
            self._respond(request_id, KEEP_OPEN)
        else:
            super()._send_response(request_id, method, result)
