"""Small stdio client for the official Codex app-server; authentication stays with Codex."""
import json
import os
import queue
import re
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
        self.args, self.env, self.cwd, self.notify = args, env, cwd, notify
        self._start()
        config = self.request('config/read', {'includeLayers': False}).get('config', {})
        servers = config.get('mcp_servers') or {}
        if servers:
            self.close()
            for name in servers:
                if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
                    raise ReviewError('An external MCP server name cannot be isolated safely. Rename it using letters, digits, hyphens or underscores.')
                self.args += ['-c', 'mcp_servers.' + name + '.enabled=false']
            self._start()
            config = self.request('config/read', {'includeLayers': False}).get('config', {})
            if any(v.get('enabled', True) for v in (config.get('mcp_servers') or {}).values()):
                self.close()
                raise ReviewError('Could not isolate the in-app research tools. Update Codex CLI and retry.')

    def _start(self):
        self.process = subprocess.Popen(self.args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, cwd=self.cwd, env=self.env)
        self.messages, self.next_id = queue.Queue(), 0
        self.tool = None
        threading.Thread(target=self._read, args=(self.process, self.messages), daemon=True).start()
        self.request('initialize', {'clientInfo': {'name': 'people_for_luma', 'title': 'People for Luma', 'version': '0.3.0'},
                                    'capabilities': {'experimentalApi': True}})
        self.send({'method': 'initialized', 'params': {}})

    def _read(self, process, messages):
        try:
            for line in process.stdout:
                try:
                    messages.put(json.loads(line))
                except ValueError:
                    continue
        finally:
            messages.put(None)

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
