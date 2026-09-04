"""TextExpander CSV, legacy plain-text plist groups, and native JSON import."""
import csv
import io
import json
import plistlib
import re
from pathlib import Path


def normalize(name, text, abbr='', group='Imported', note=''):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('A snippet has no plain-text content. Export this group as CSV first.')
    if re.search(r'%(?:fill|snippet|key|script|[YymdHIMSABaep]|clipboard|\(|\{|\d)', text):
        note = (note + '\nContains TextExpander macros. Convert these before enabling expansion.').strip()
    if re.search(r'<(?:html|body|div|span|p|br|img|b|a)\b|\\rtf', text, re.I):
        note = (note + '\nRich formatting detected; imported as source text. Review and convert to plain text.').strip()
    return dict(name=str(name or abbr or text.splitlines()[0][:65]), text=text,
                abbreviation=str(abbr or ''), group_name=str(group or 'Imported'),
                enabled=not bool(note), note=note)


def parse_file(path):
    path = Path(path)
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError('Please import a file smaller than 50 MB, or split it into groups.')
    data = path.read_bytes()
    group = path.stem
    if path.suffix.lower() == '.json':
        source = json.loads(data)
        rows = source.get('snippets', []) if isinstance(source, dict) else source
        if not isinstance(rows, list):
            raise ValueError('Expected a JSON snippet list.')
        result = []
        for row in rows:
            item = normalize(row.get('name'), row.get('text', row.get('content')), row.get('abbreviation'),
                             row.get('group_name', group), row.get('note', ''))
            item.update(favorite=bool(row.get('favorite')), enabled=bool(row.get('enabled', True)) and not item['note'])
            result.append(item)
    elif path.suffix.lower() in ('.textexpander', '.plist') or data.startswith(b'bplist'):
        source = plistlib.loads(data)
        result = []
        def walk(obj, current_group):
            if isinstance(obj, dict):
                current_group = obj.get('groupName', current_group)
                if 'plainText' in obj:
                    result.append(normalize(obj.get('label'), obj['plainText'], obj.get('abbreviation'), current_group))
                else:
                    for value in obj.values():
                        walk(value, current_group)
            elif isinstance(obj, list):
                for value in obj:
                    walk(value, current_group)
        walk(source, group)
    else:
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = data.decode('utf-16')
        try:
            dialect = csv.Sniffer().sniff(text[:10000], delimiters=',\t;')
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(io.StringIO(text, newline=''), dialect))
        rows = [r for r in rows if any(c.strip() for c in r)]
        if not rows:
            raise ValueError('This file contains no snippets.')
        aliases = {'abbreviation':'abbr','abbreviations':'abbr','shortcut':'abbr','trigger':'abbr',
                   'content':'text','snippet':'text','snippet content':'text','body':'text','text':'text','plain text':'text',
                   'label':'name','name':'name','title':'name','group':'group','group name':'group'}
        header = [aliases.get(c.strip().lower(), '') for c in rows[0]]
        has_header = 'text' in header and ('abbr' in header or 'name' in header)
        result = []
        for n, row in enumerate(rows[1:] if has_header else rows, 2 if has_header else 1):
            if len(row) < 2:
                raise ValueError(f'CSV row {n} needs at least abbreviation and content columns.')
            if has_header:
                mapped = {header[i]:value for i,value in enumerate(row) if i < len(header) and header[i]}
            else:
                mapped = dict(zip(['abbr','text','name','group'], row))
            result.append(normalize(mapped.get('name'), mapped.get('text'), mapped.get('abbr'), mapped.get('group', group)))
    if not result:
        raise ValueError('No plain-text snippets found. Use TextExpander’s CSV export.')
    return result
