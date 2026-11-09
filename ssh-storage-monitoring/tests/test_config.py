import json
import tempfile
import unittest
from pathlib import Path
from main import disk_command, load_servers, select_servers


class ConfigTests(unittest.TestCase):
    def test_disk_commands(self):
        self.assertEqual(disk_command(True), 'df -hP /')
        self.assertEqual(disk_command(False), 'df -hP')

    def test_selection(self):
        servers = [{'name': 'a'}, {'name': 'b'}]
        self.assertEqual(select_servers(servers, ['b']), [{'name': 'b'}])
        with self.assertRaises(ValueError):
            select_servers(servers, ['unknown'])

    def test_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'config.json'
            p.write_text(json.dumps({'servers': [{'name': 'a', 'host': 'example.org', 'username': 'monitor'}]}))
            self.assertEqual(load_servers(p)[0]['name'], 'a')


if __name__ == '__main__':
    unittest.main()
