import asyncio
import base64
import json
import struct
from typing import List, Optional, Tuple

import pandas as pd
from solana.exceptions import SolanaRpcException
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.rpc.async_api import AsyncClient
from solana.rpc.core import RPCException
from solana.system_program import (CreateAccountWithSeedParams,
                                   create_account_with_seed)
from solana.transaction import AccountMeta, Transaction, TransactionInstruction

from liualgotrader.common.tlog import tlog


def load_wallet(wallet_filename: str) -> Keypair:
    with open(wallet_filename) as f:
        data = json.load(f)

        return Keypair.from_secret_key(bytes(data))


async def _retry(coro, *args):
    result = None
    while not result:
        try:
            return await coro(*args)
        except SolanaRpcException as e:
            tlog(f"Error {e} for {coro} retrying after short nap")
            await asyncio.sleep(10 + random.randint(0, 10))

    return result


async def set_response_account(
    client: AsyncClient, payer: Keypair, program_publicKey: PublicKey
) -> PublicKey:
    response_size = 4 * 2
    rent_lamports = (
        await _retry(
            client.get_minimum_balance_for_rent_exemption, response_size
        )
    )["result"]

    response_key = PublicKey.create_with_seed(
        payer.public_key, "hello9", program_publicKey
    )

    instruction = create_account_with_seed(
        CreateAccountWithSeedParams(
            from_pubkey=payer.public_key,
            new_account_pubkey=response_key,
            base_pubkey=payer.public_key,
            seed="hello9",
            lamports=rent_lamports,
            space=response_size,
            program_id=program_publicKey,
        )
    )
    trans = Transaction().add(instruction)
    try:
        trans_result = await _retry(client.send_transaction, trans, payer)
        await _retry(
            client.confirm_transaction,
            trans_result["result"],
            "finalized",
            5.0,
        )
    except RPCException:
        None

    return response_key


def _symbol_to_bytes(data: pd.DataFrame) -> bytes:
    raw_data = [
        (int(x), int(str(round(x, 2)).split(".")[1])) for x in data.to_list()
    ]
    whole, _ = zip(*raw_data)

    bytes_data: List = []
    if max(whole) >= 256:
        for tup in raw_data:
            bytes_data.append(tup[0] // 256)
            bytes_data.append(tup[0] % 256)
            bytes_data.append(tup[1])
        return bytes([1] + bytes_data)
    else:
        for tup in raw_data:
            bytes_data.append(tup[0])
            bytes_data.append(tup[1])

        return bytes([0] + bytes_data)


async def _parse_response(
    client: AsyncClient, response_key: PublicKey
) -> Tuple:
    base64_result = (await _retry(client.get_account_info, response_key))[
        "result"
    ]["value"]["data"]
    return struct.unpack(
        "ff", base64.b64decode(base64_result[0])
    )  # type ignore


async def get_program_result(
    client: AsyncClient,
    program_key: PublicKey,
    response_key: PublicKey,
    payer: Keypair,
    data: pd.DataFrame,
) -> Optional[Tuple]:

    payload_to_contract: bytes = _symbol_to_bytes(data)
    instruction = TransactionInstruction(
        keys=[
            AccountMeta(
                pubkey=response_key,
                is_signer=False,
                is_writable=True,
            ),
        ],
        program_id=program_key,
        data=payload_to_contract,
    )
    recent_blockhash = (await _retry(client.get_recent_blockhash))["result"][
        "value"
    ]["blockhash"]
    trans = Transaction(
        recent_blockhash=recent_blockhash, fee_payer=payer.public_key
    ).add(instruction)

    try:
        trans_result = await _retry(client.send_transaction, trans, payer)
    except RPCException as e:
        tlog(
            f"SOLANA ERROR {e} for payload of {len(payload_to_contract)} bytes"
        )
        return None

    await _retry(
        client.confirm_transaction, trans_result["result"], "finalized", 5.0
    )

    return await _parse_response(client, response_key)
