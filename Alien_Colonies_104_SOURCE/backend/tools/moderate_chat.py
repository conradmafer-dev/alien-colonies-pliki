#!/usr/bin/env python3
"""Local operator CLI for chat reports. Requires direct access to the server DB.
Never exposed as an HTTP endpoint. Examples:
  python tools/moderate_chat.py --db /data/private_test.sqlite3 reports
  python tools/moderate_chat.py --db /data/private_test.sqlite3 remove 123
  python tools/moderate_chat.py --db /data/private_test.sqlite3 mute PLAYER_ID --hours 24
"""
import argparse
import json
from pathlib import Path
import sqlite3
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True,type=Path)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('reports')
    remove=commands.add_parser('remove');remove.add_argument('message_id',type=int)
    dismiss=commands.add_parser('dismiss');dismiss.add_argument('message_id',type=int)
    mute=commands.add_parser('mute');mute.add_argument('player_id');mute.add_argument('--hours',type=float,default=24)
    unmute=commands.add_parser('unmute');unmute.add_argument('player_id')
    args=parser.parse_args()
    if not args.db.is_file(): parser.error('Database does not exist.')
    with sqlite3.connect(args.db,timeout=10) as db:
        db.execute('PRAGMA foreign_keys=ON')
        if args.command=='reports':
            rows=db.execute('''SELECT m.id,m.sender,m.recipient,m.body,m.created,COUNT(*) AS reports
                FROM chat_reports r JOIN chat_messages m ON m.id=r.message_id
                GROUP BY m.id ORDER BY reports DESC,m.id DESC LIMIT 100''').fetchall()
            print(json.dumps([dict(zip(['id','sender','recipient','text','at','reports'],row)) for row in rows],ensure_ascii=False,indent=2))
        elif args.command=='remove':
            changed=db.execute('DELETE FROM chat_messages WHERE id=?',(args.message_id,)).rowcount
            print(f'Removed messages: {changed}')
        elif args.command=='dismiss':
            changed=db.execute('DELETE FROM chat_reports WHERE message_id=?',(args.message_id,)).rowcount
            print(f'Dismissed reports: {changed}')
        elif args.command=='mute':
            if not 0 < args.hours <= 8760: parser.error('--hours must be between 0 and 8760.')
            if not db.execute('SELECT 1 FROM accounts WHERE id=?',(args.player_id,)).fetchone(): parser.error('Player does not exist.')
            db.execute('''INSERT INTO chat_mutes VALUES(?,?) ON CONFLICT(player_id)
                DO UPDATE SET until=excluded.until''',(args.player_id,time.time()+args.hours*3600))
            print('Player muted.')
        elif args.command=='unmute':
            db.execute('DELETE FROM chat_mutes WHERE player_id=?',(args.player_id,))
            print('Mute removed.')

if __name__=='__main__': main()
