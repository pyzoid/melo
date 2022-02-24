import asyncio 

async def await_me_maybe(func, **kwargs):
    if callable(func):
        value = func(**kwargs)
    if asyncio.iscoroutine(value):
        value = await value
    return value
