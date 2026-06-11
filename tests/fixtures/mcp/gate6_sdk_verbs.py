"""GATE 6 fixture: narrow SDK verbs recognised on any receiver.

Each @mcp.tool exposes a distinct narrow verb from the GATE 6 breadth:
  - execute_query / execute_param_query → database_write
  - sendall / send_command              → destructive (socket / RPC egress)
  - start_execution                     → destructive (state machine kickoff)

All five tools must surface as UNGUARDED (verb is unambiguous; no guards).
"""
from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("gate6-verbs")


@mcp.tool()
async def do_query(driver, sql: str) -> list:
    return await driver.execute_query(sql)


@mcp.tool()
async def do_param_query(driver, sql: str, params: tuple) -> list:
    return await driver.execute_param_query(sql, params)


@mcp.tool()
def do_sendall(sock, payload: bytes) -> None:
    sock.sendall(payload)


@mcp.tool()
def do_send_command(channel, cmd: str) -> str:
    return channel.send_command(cmd)


@mcp.tool()
def do_start_execution(sfn_client, arn: str, payload: dict) -> dict:
    return sfn_client.start_execution(stateMachineArn=arn, input=payload)
