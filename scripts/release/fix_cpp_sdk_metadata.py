#!/usr/bin/env python3
"""Make bundled IXWebSocket pkg-config metadata relocatable for a pinned SDK build."""
import argparse,pathlib,re
p=argparse.ArgumentParser(description=__doc__);p.add_argument('sdk',type=pathlib.Path);p.add_argument('--ix-version',required=True);a=p.parse_args()
if not re.fullmatch(r'\d+\.\d+\.\d+',a.ix_version):raise ValueError('Use the actual pinned IXWebSocket version')
path=a.sdk/'lib/pkgconfig/ixwebsocket.pc'
if not path.is_file() or path.is_symlink():raise ValueError('Expected SDK pkg-config metadata missing')
s=path.read_text()
if 'Name: ixwebsocket' not in s:raise ValueError('Unexpected pkg-config package')
s=re.sub(r'^prefix=.*$',r'prefix=${pcfiledir}/../..',s,flags=re.M)
s=re.sub(r'^Version:.*$','Version: '+a.ix_version,s,flags=re.M)
path.write_text(s);print('SDK pkg-config prefix is relative; dependency version recorded')
