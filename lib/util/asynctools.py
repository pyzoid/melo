import asyncio 

async def await_me_maybe(value):
    if callable(value):
        value = value()
    if asyncio.iscoroutine(value):
        value = await value
    return value
