"""Authenticated public chat and participant-only direct messages.

Chat stays in indexed SQLite tables, outside the gameplay snapshot. World owns
locking, transactions, the account lifecycle and the injectable real-time clock.
"""
import re
import unicodedata

try:
    from .i18n import t
except ImportError:
    from i18n import t

MAX_MESSAGE_LENGTH = 500
HISTORY_DAYS = 30
PAGE_SIZE = 50


class CommunicationsMixin:
    def _init_communications(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                recipient TEXT REFERENCES accounts(id) ON DELETE CASCADE,
                body TEXT NOT NULL, created REAL NOT NULL, request_id TEXT NOT NULL,
                UNIQUE(sender, request_id)
            );
            CREATE INDEX IF NOT EXISTS chat_recipient ON chat_messages(recipient,id);
            CREATE INDEX IF NOT EXISTS chat_sender ON chat_messages(sender,id);
            CREATE INDEX IF NOT EXISTS chat_created ON chat_messages(created);
            CREATE TABLE IF NOT EXISTS chat_reads (
                owner TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                channel TEXT NOT NULL, last_id INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(owner,channel)
            );
            CREATE TABLE IF NOT EXISTS chat_visibility (
                owner TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
                after_id INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS chat_blocks (
                owner TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                blocked TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                PRIMARY KEY(owner,blocked)
            );
            CREATE TABLE IF NOT EXISTS chat_reports (
                reporter TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                message_id INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
                created REAL NOT NULL, PRIMARY KEY(reporter,message_id)
            );
            CREATE TABLE IF NOT EXISTS chat_mutes (
                player_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
                until REAL NOT NULL
            );
        """)
        # Upgrades and newly created accounts start without historical badges.
        self.db.execute("""INSERT OR IGNORE INTO chat_reads(owner,channel,last_id)
            SELECT id,'',COALESCE((SELECT MAX(id) FROM chat_messages WHERE recipient IS NULL),0)
            FROM accounts""")

    def _chat_register(self, player_id):
        # Capture the account's immutable history boundary in its registration
        # transaction. Message IDs, unlike timestamps, order messages sent in
        # the same clock tick. Read markers may change without exposing history.
        self.db.execute("""INSERT OR IGNORE INTO chat_visibility(owner,after_id)
            VALUES(?, COALESCE((SELECT MAX(id) FROM chat_messages),0))""", (player_id,))
        self.db.execute("""INSERT OR IGNORE INTO chat_reads VALUES(?, '',
            COALESCE((SELECT MAX(id) FROM chat_messages WHERE recipient IS NULL),0))""", (player_id,))
        self._alliance_register_chat_visibility(player_id)

    def _chat_peer(self, player_id, peer):
        self._player(player_id)
        if not isinstance(peer, str):
            raise self.account_error_class(t('Nieprawidłowy rozmówca.'), 400)
        if peer and (peer == player_id or peer not in self.data['players']):
            raise self.account_error_class(t('Nie znaleziono rozmówcy.'), 404)
        return peer

    def _chat_channel(self, player_id, peer):
        if peer:
            return ('((m.sender=? AND m.recipient=?) OR (m.sender=? AND m.recipient=?))',
                    [player_id, peer, peer, player_id])
        # Accounts created before this boundary existed retain their history.
        return ('''m.recipient IS NULL
            AND m.id>COALESCE((SELECT after_id FROM chat_visibility WHERE owner=?),0)
            AND NOT EXISTS
            (SELECT 1 FROM chat_blocks b WHERE b.owner=? AND b.blocked=m.sender)''',
            [player_id, player_id])

    def _chat_blocked(self, player_id, peer):
        return bool(peer and self.db.execute('''SELECT 1 FROM chat_blocks
            WHERE (owner=? AND blocked=?) OR (owner=? AND blocked=?)''',
            (player_id, peer, peer, player_id)).fetchone())

    def _chat_permissions(self, player_id, peer):
        muted = self.db.execute('SELECT until FROM chat_mutes WHERE player_id=?', (player_id,)).fetchone()
        until = float(muted[0]) if muted else 0.0
        own_block = bool(peer and self.db.execute('SELECT 1 FROM chat_blocks WHERE owner=? AND blocked=?',
                                                 (player_id, peer)).fetchone())
        return {'blocked_by_you': own_block, 'muted_until': until,
                'can_send': until <= self.now and not self._chat_blocked(player_id, peer)}

    def _chat_public_message(self, row):
        return {'id': row[0], 'sender_id': row[1], 'sender_name': self._player(row[1])['name'],
                'peer_id': row[2] or '', 'text': row[3], 'at': row[4]}

    def chat_summary(self, player_id):
        with self.lock:
            self._player(player_id)
            counts = self.db.execute('''SELECT m.recipient IS NULL, COUNT(*)
                FROM chat_messages m LEFT JOIN chat_reads r ON r.owner=? AND
                r.channel=CASE WHEN m.recipient IS NULL THEN '' ELSE m.sender END
                WHERE (m.recipient IS NULL OR m.recipient=?) AND m.sender<>?
                AND (m.recipient IS NOT NULL OR
                     m.id>COALESCE((SELECT after_id FROM chat_visibility WHERE owner=?),0))
                AND m.id>COALESCE(r.last_id,0) AND m.created>=?
                AND NOT EXISTS(SELECT 1 FROM chat_blocks b WHERE b.owner=? AND b.blocked=m.sender)
                GROUP BY m.recipient IS NULL''',
                (player_id, player_id, player_id, player_id,
                 self.now-HISTORY_DAYS*86400, player_id)).fetchall()
            values = dict(counts)
            public, private = values.get(1, 0), values.get(0, 0)
            return {'available': True, 'global_unread': public, 'private_unread': private,
                    'unread': public+private, 'max_length': MAX_MESSAGE_LENGTH}

    def chat_feed(self, player_id, peer='', before=0, after=0):
        with self.lock:
            peer = self._chat_peer(player_id, peer)
            for value in (before, after):
                if type(value) is not int or value < 0 or value > 9_223_372_036_854_775_807:
                    raise self.account_error_class(t('Nieprawidłowy numer wiadomości.'), 400)
            where, args = self._chat_channel(player_id, peer)
            where += ' AND m.created>=?'
            args.append(self.now-HISTORY_DAYS*86400)
            if before:
                where += ' AND m.id<?'
                args.append(before)
            if after:
                where += ' AND m.id>?'
                args.append(after)
            ascending = after > 0
            rows = self.db.execute('SELECT m.id,m.sender,m.recipient,m.body,m.created FROM chat_messages m WHERE '
                + where + (' ORDER BY m.id ASC LIMIT ?' if ascending else ' ORDER BY m.id DESC LIMIT ?'),
                (*args, PAGE_SIZE+1)).fetchall()
            more = len(rows) > PAGE_SIZE
            rows = rows[:PAGE_SIZE]
            if not ascending:
                rows.reverse()
            return {'ok': True, 'peer_id': peer,
                    'peer_name': self._player(peer)['name'] if peer else '',
                    'messages': [self._chat_public_message(row) for row in rows],
                    'has_older': more if not ascending else False,
                    'has_more': more if ascending else False,
                    'permissions': self._chat_permissions(player_id, peer),
                    'summary': self.chat_summary(player_id)}

    def chat_inbox(self, player_id):
        with self.lock:
            self._player(player_id)
            rows = self.db.execute('''SELECT m.id,m.sender,m.recipient,m.body,m.created FROM chat_messages m
                WHERE m.id IN (SELECT MAX(id) FROM chat_messages WHERE (sender=? OR recipient=?)
                AND recipient IS NOT NULL AND created>=?
                GROUP BY CASE WHEN sender=? THEN recipient ELSE sender END)
                ORDER BY m.id DESC LIMIT 100''',
                (player_id, player_id, self.now-HISTORY_DAYS*86400, player_id)).fetchall()
            threads = []
            for row in rows:
                peer = row[2] if row[1] == player_id else row[1]
                unread = self.db.execute('''SELECT COUNT(*) FROM chat_messages WHERE recipient=? AND sender=?
                    AND id>COALESCE((SELECT last_id FROM chat_reads WHERE owner=? AND channel=?),0)
                    AND created>=?''', (player_id, peer, player_id, peer, self.now-HISTORY_DAYS*86400)).fetchone()[0]
                permissions = self._chat_permissions(player_id, peer)
                threads.append({'peer_id': peer, 'name': self._player(peer)['name'], 'at': row[4],
                    'preview': row[3][:80], 'unread': 0 if permissions['blocked_by_you'] else unread,
                    **permissions})
            return {'ok': True, 'threads': threads, 'summary': self.chat_summary(player_id)}

    def chat_send(self, player_id, payload):
        with self.lock, self._atomic():
            peer = self._chat_peer(player_id, payload.get('peer_id', ''))
            text, request_id = payload.get('text'), payload.get('request_id')
            if not isinstance(text, str) or len(text) > MAX_MESSAGE_LENGTH:
                raise self.account_error_class(t('Wiadomość może mieć od 1 do 500 znaków.'), 400)
            text = unicodedata.normalize('NFC', ''.join(c for c in text.replace('\r\n', '\n').replace('\t', ' ')
                    if c == '\n' or unicodedata.category(c) not in ('Cc', 'Cs'))).strip()
            if not text or len(text) > MAX_MESSAGE_LENGTH or text.count('\n') > 8:
                raise self.account_error_class(t('Wiadomość może mieć od 1 do 500 znaków.'), 400)
            if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{8,96}', request_id):
                raise self.account_error_class(t('Nieprawidłowy identyfikator wiadomości.'), 400)
            old = self.db.execute('SELECT id,sender,recipient,body,created FROM chat_messages WHERE sender=? AND request_id=?',
                                  (player_id, request_id)).fetchone()
            if old:
                if (old[2] or '') != peer or old[3] != text:
                    raise self.account_error_class(t('Identyfikator wiadomości jest już użyty.'), 409)
                return {'ok': True, 'sent': self._chat_public_message(old), 'summary': self.chat_summary(player_id)}
            if not self._chat_permissions(player_id, peer)['can_send']:
                raise self.account_error_class(t('Wysyłanie wiadomości jest obecnie zablokowane.'), 403)
            times = self.db.execute('SELECT created FROM chat_messages WHERE sender=? AND created>? ORDER BY id DESC',
                                    (player_id, self.now-3600)).fetchall()
            if times and self.now-times[0][0] < 3 or len(times) >= 120 or sum(at[0] > self.now-60 for at in times) >= 20:
                raise self.account_error_class(t('Piszesz zbyt szybko. Spróbuj za chwilę.'), 429)
            self.db.execute('DELETE FROM chat_messages WHERE created<?', (self.now-HISTORY_DAYS*86400,))
            cursor = self.db.execute('INSERT INTO chat_messages(sender,recipient,body,created,request_id) VALUES(?,?,?,?,?)',
                                     (player_id, peer or None, text, self.now, request_id))
            # Bound the shared feed so ordinary world polls never scan an unlimited chat log.
            self.db.execute('''DELETE FROM chat_messages WHERE recipient IS NULL AND id <=
                (SELECT id FROM chat_messages WHERE recipient IS NULL ORDER BY id DESC LIMIT 1 OFFSET 1000)''')
            row = (cursor.lastrowid, player_id, peer or None, text, self.now)
            self._touch_player_activity(player_id)
            return {'ok': True, 'sent': self._chat_public_message(row), 'summary': self.chat_summary(player_id)}

    def chat_read(self, player_id, payload):
        with self.lock, self._atomic():
            peer = self._chat_peer(player_id, payload.get('peer_id', ''))
            last_id = payload.get('last_id')
            if type(last_id) is not int or not 0 <= last_id <= 9_223_372_036_854_775_807:
                raise self.account_error_class(t('Nieprawidłowy numer wiadomości.'), 400)
            where, args = self._chat_channel(player_id, peer)
            bounded = self.db.execute('SELECT COALESCE(MAX(m.id),0) FROM chat_messages m WHERE '+where+' AND m.id<=?',
                                      (*args, last_id)).fetchone()[0]
            self.db.execute('''INSERT INTO chat_reads VALUES(?,?,?) ON CONFLICT(owner,channel)
                DO UPDATE SET last_id=MAX(chat_reads.last_id,excluded.last_id)''', (player_id, peer, bounded))
            return {'ok': True, 'summary': self.chat_summary(player_id)}

    def chat_block(self, player_id, payload):
        with self.lock, self._atomic():
            peer = self._chat_peer(player_id, payload.get('peer_id', ''))
            blocked = payload.get('blocked')
            if not peer or type(blocked) is not bool:
                raise self.account_error_class(t('Nieprawidłowy rozmówca.'), 400)
            if blocked:
                changed = self.db.execute('INSERT OR IGNORE INTO chat_blocks VALUES(?,?)', (player_id, peer)).rowcount
            else:
                changed = self.db.execute('DELETE FROM chat_blocks WHERE owner=? AND blocked=?', (player_id, peer)).rowcount
            if changed:
                self._touch_player_activity(player_id)
            return {'ok': True, 'summary': self.chat_summary(player_id)}

    def chat_report(self, player_id, payload):
        with self.lock, self._atomic():
            self._player(player_id)
            message_id = payload.get('message_id')
            if type(message_id) is not int or not 0 < message_id <= 9_223_372_036_854_775_807:
                raise self.account_error_class(t('Nieprawidłowy numer wiadomości.'), 400)
            row = self.db.execute('''SELECT sender,recipient FROM chat_messages WHERE id=?
                AND (recipient IS NOT NULL OR
                     id>COALESCE((SELECT after_id FROM chat_visibility WHERE owner=?),0))''',
                (message_id, player_id)).fetchone()
            if not row or row[0] == player_id or (row[1] is not None and player_id not in row):
                raise self.account_error_class(t('Nie znaleziono wiadomości.'), 404)
            if self.db.execute('SELECT COUNT(*) FROM chat_reports WHERE reporter=? AND created>?',
                               (player_id, self.now-3600)).fetchone()[0] >= 20:
                raise self.account_error_class(t('Piszesz zbyt szybko. Spróbuj za chwilę.'), 429)
            if self.db.execute('INSERT OR IGNORE INTO chat_reports VALUES(?,?,?)', (player_id, message_id, self.now)).rowcount:
                self._touch_player_activity(player_id)
            return {'ok': True, 'message': t('Wiadomość została zgłoszona.')}
