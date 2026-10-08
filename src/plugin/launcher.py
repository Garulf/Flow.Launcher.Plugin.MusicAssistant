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
    * A cancelled request is answered with ``"result": null`` next to the
      error. StreamJsonRpc reads ``result`` first, so Flow takes it as a null
      query response and fails. Error replies are sent without ``result``.
    """

    def __init__(self) -> None:
        super().__init__()
        self.action_keyword = ""
        self.settings_dir: Optional[str] = None
        messages = self._client.messages
        send = self._client.send

        def send_valid_envelope(message: dict) -> None:
            if message.get("error") is not None:
                message = {key: value for key, value in message.items() if key != "result"}
            send(message)

        async def observed_messages():
            async for request in messages():
                self._observe(request)
                yield request

        self._client.messages = observed_messages
        self._client.send = send_valid_envelope

    def _observe(self, request: dict) -> None:
        method = request.get("method")
        params = request.get("params")
        if method not in ("query", "initialize") or not isinstance(params, list) or not params:
            return
        if not isinstance(params[0], dict):
            return
        if method == "query":
            self.action_keyword = params[0].get("actionKeyword") or ""
        else:
            metadata = params[0].get("currentPluginMetadata") or {}
            self.settings_dir = metadata.get("pluginSettingsDirectoryPath") or None

    def _send_response(self, request_id, method, result):
        if result == KEEP_OPEN:
            self._respond(request_id, KEEP_OPEN)
        else:
            super()._send_response(request_id, method, result)
