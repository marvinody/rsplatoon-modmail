"""
r/Splatoon ModMail Bot, Database module

 DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
                   Version 2, December 2004

Copyright (C) 2004 Sam Hocevar <sam@hocevar.net>

Everyone is permitted to copy and distribute verbatim or modified
copies of this license document, and changing it is allowed as long
as the name is changed.

           DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
  TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

 0. You just DO WHAT THE FUCK YOU WANT TO.
"""

import os
from typing import Optional, Tuple
from unittest.mock import sentinel

from cachetools import LRUCache

from datetime import datetime

import aiosqlite


class Database:
    _fp = os.environ.get("REPORT_DB", "reports.sqlite")
    _conn: aiosqlite.Connection

    @classmethod
    async def connect(cls):
        # noinspection PyTypeChecker
        cls._conn: aiosqlite.Connection = await aiosqlite.connect(cls._fp)

    @classmethod
    async def close(cls):
        await cls._conn.close()

    @classmethod
    async def execute(cls, query, *params):
        async with cls._conn.cursor() as cur:
            if len(params) > 1:
                await cur.executemany(query, params)
            elif len(params) == 1:
                await cur.execute(query, params[0])
            else:
                await cur.execute(query)
        await cls._conn.commit()

    @classmethod
    async def fetchone(cls, query, params=None):
        async with cls._conn.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchone()

    @classmethod
    async def fetchall(cls, query, params=None):
        async with cls._conn.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchall()


async def init_tables():
    q = """
        CREATE TABLE IF NOT EXISTS `threads` (
            `owner_id` BIGINT UNSIGNED PRIMARY KEY,
            `named_thread_id` BIGINT UNSIGNED NULL DEFAULT NULL,
            `anon_thread_id` BIGINT UNSIGNED NULL DEFAULT NULL,
            `flags` TINYINT UNSIGNED NOT NULL DEFAULT 0
        );
    """
    await Database.execute(q)


_cache = LRUCache(64)
_user_cache = LRUCache(64)


class UserFlags:
    def __init__(self, value):
        self._value = value

    def __int__(self):
        return self._value

    def _bit(self, bit):
        return (self._value >> bit) & 1

    def _set(self, bit, value):
        if value is True or value == 1:
            self._value |= (1 << bit)
        elif value is False or value == 0:
            self._value &= ~(1 << bit)
        else:
            raise ValueError()

    @property
    def open_named(self):
        return self._bit(0)

    @open_named.setter
    def open_named(self, value):
        if self._bit(1):
            raise RuntimeError("Cannot set named when anon is set")
        self._set(0, value)

    @property
    def open_anon(self):
        return self._bit(1)

    @open_anon.setter
    def open_anon(self, value):
        if self._bit(0):
            raise RuntimeError("Cannot set anon when named is set")
        self._set(1, value)

    @property
    def banned(self):
        return self._bit(2)

    @banned.setter
    def banned(self, value):
        self._set(2, value)

    @property
    def individual_staff(self):
        return self._bit(3)

    @individual_staff.setter
    def individual_staff(self, value):
        self._set(3, value)

    @property
    def muted(self):
        return self._bit(4)

    @muted.setter
    def muted(self, value):
        self._set(4, value)


async def get_user_threads(user_id) -> Tuple[Optional[int], Optional[int], UserFlags]:
    if user_id in _cache:
        return _cache[user_id]

    q = "SELECT named_thread_id, anon_thread_id, flags FROM threads WHERE owner_id = ?"
    resp = await Database.fetchone(q, (user_id,))

    if resp is None:
        resp = (None, None, 0)

    _cache[user_id] = (resp[0], resp[1], UserFlags(resp[2]))
    return _cache[user_id]


async def get_thread_user(thread_id) -> Optional[Tuple[int, UserFlags]]:
    if thread_id in _user_cache:
        return _user_cache[thread_id]

    q = "SELECT owner_id, flags FROM threads WHERE named_thread_id = ? or anon_thread_id = ?"
    resp = await Database.fetchone(q, (thread_id, thread_id))

    if resp is None:
        resp = (None, 0)

    _user_cache[thread_id] = (resp[0], UserFlags(resp[1]))
    return _user_cache[thread_id]


MISSING = sentinel.MISSING


async def save_user_threads(user_id, named=MISSING, anon=MISSING, flags=MISSING):
    threads = await get_user_threads(user_id)
    threads = list(threads)
    if named is not MISSING:
        threads[0] = named
    if anon is not MISSING:
        threads[1] = anon
    if flags is not MISSING:
        threads[2] = flags

    _cache[user_id] = tuple(threads)
    q = """INSERT OR REPLACE INTO threads (owner_id, named_thread_id, anon_thread_id, flags) VALUES (?, ?, ?, ?)"""
    await Database.execute(q, (user_id, threads[0], threads[1], int(threads[2])))
