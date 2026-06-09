from __future__ import annotations


async def run_query(conn, query):
    await conn.execute("SET TRANSACTION READ ONLY")  # must NOT be a side effect
    return await conn.fetch(query)  # read, not a side effect


async def run_write(conn, value):
    await conn.execute("SET TRANSACTION READ ONLY")  # must NOT be a side effect
    await conn.execute("INSERT INTO t VALUES ($1)", value)  # real write
    return True
