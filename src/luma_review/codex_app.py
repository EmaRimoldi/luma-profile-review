"""Small stdio client for the official Codex app-server; authentication stays with Codex."""
import json
import os
import queue
import shutil
import subprocess
import threading
import time

from .core import ReviewError


class CodexApp:
    def __init__(self, cwd, notify=lambda method, params: None):
        executable = shutil.which('codex')
        if not executable:
            raise ReviewError('Install Codex CLI to connect your ChatGPT account.')
        # Fixed configuration: model-controlled shell commands and external MCP servers are disabled.
        args = [executable, 'app-server', '--listen', 'stdio://',
                '-c', 'features.shell_tool=false', '-c', 'features.apply_patch_freeform=false',
                '-c', 'web_search="disabled"', '-c', 'mcp_servers={}', '-c', 'features.apps=false']
        env = {k: v for k, v in os.environ.items() if k not in {'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'}}
        self.process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, cwd=cwd, env=env)
        self.messages, self.next_id, self.notify = queue.Queue(), 0, notify
        self.tool = None
        threading.Thread(target=self._read, daemon=True).start()
        self.request('initialize', {'clientInfo': {'name': 'people_for_luma', 'title': 'People for Luma', 'version': '0.3.0'},
                                    'capabilities': {'experimentalApi': True}})
        self.send({'method': 'initialized', 'params': {}})

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except ValueError:
                    continue
        finally:
            self.messages.put(None)

    def send(self, value):
        if self.process.poll() is not None:
            raise ReviewError('Codex disconnected. Reconnect to continue.')
        self.process.stdin.write(json.dumps(value) + '\n')
        self.process.stdin.flush()

    def receive(self, timeout=1):
        try:
            value = self.messages.get(timeout=timeout)
        except queue.Empty:
            return {}
        if value is None:
            raise ReviewError('Codex disconnected. Reconnect to continue.')
        if 'method' in value:
            method, params = value['method'], value.get('params', {})
            if 'id' in value:
                if method == 'item/tool/call' and self.tool:
                    try:
                        output = self.tool(params['tool'], params['arguments'])
                        result = {'success': True, 'contentItems': [{'type': 'inputText', 'text': json.dumps(output, ensure_ascii=False)}]}
                    except Exception as error:
                        result = {'success': False, 'contentItems': [{'type': 'inputText', 'text': str(error)[:1000]}]}
                    self.send({'id': value['id'], 'result': result})
                else:
                    # No unattended shell, filesystem, or third-party approval grants.
                    self.send({'id': value['id'], 'error': {'code': -32601, 'message': 'Only the in-app research tools are available.'}})
            else:
                self.notify(method, params)
        return value

    def request(self, method, params=None, timeout=40):
        self.next_id += 1
        ident = self.next_id
        self.send({'id': ident, 'method': method, 'params': params or {}})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.receive()
            if value.get('id') == ident and 'method' not in value:
                if value.get('error'):
                    raise ReviewError('Codex could not complete this request. Check the CLI version and account connection.')
                return value.get('result', {})
        raise ReviewError('Codex did not respond in time. Reconnect to continue.')

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process.stdin.close()
        self.process.stdout.close()
