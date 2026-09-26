import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from payment_service.workers import payment_execution as module


def factory() -> Mock:
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.begin = Mock(return_value=AsyncMock())
    return Mock(return_value=session)


def worker() -> module.PaymentExecutionWorker:
    return module.PaymentExecutionWorker(factory(), object(), 10, 0.1, 30)


async def test_worker_loads_runnable_ids_in_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    payment_id = uuid4()
    repository = SimpleNamespace(get_runnable_ids=AsyncMock(return_value=[payment_id]))
    monkeypatch.setattr(module, "PaymentRepository", lambda _session: repository)
    payment_worker = worker()

    assert await payment_worker._get_runnable_ids() == [payment_id]
    repository.get_runnable_ids.assert_awaited_once_with(limit=10)


async def test_worker_executes_payment_via_service(monkeypatch: pytest.MonkeyPatch) -> None:
    execute = AsyncMock(return_value=True)
    monkeypatch.setattr(
        module, "PaymentExecuteService", lambda **_kwargs: SimpleNamespace(execute=execute)
    )
    payment_worker = worker()
    payment_id = uuid4()

    assert await payment_worker._execute_payment(payment_id) is True
    execute.assert_awaited_once_with(payment_id)


@pytest.mark.parametrize("processing_fails", [False, True])
async def test_worker_keeps_polling_after_one_payment_error(
    monkeypatch: pytest.MonkeyPatch, processing_fails: bool
) -> None:
    payment_worker = worker()
    payment_id = uuid4()
    payment_worker._get_runnable_ids = AsyncMock(return_value=[payment_id])
    execute = AsyncMock(side_effect=RuntimeError("provider down") if processing_fails else None)
    payment_worker._execute_payment = execute
    sleep = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(
        module, "asyncio", SimpleNamespace(CancelledError=asyncio.CancelledError, sleep=sleep)
    )

    with pytest.raises(asyncio.CancelledError):
        await payment_worker.run()

    execute.assert_awaited_once_with(payment_id)
    sleep.assert_awaited_once_with(0.1)


async def test_worker_main_disposes_engine_after_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    dispose = AsyncMock()
    run = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(module, "Settings", lambda: SimpleNamespace(
        fake_payment_should_succeed=True,
        fake_payment_delay_seconds=0,
        payment_execution_batch_size=10,
        payment_execution_poll_interval_seconds=1,
        payment_processing_lease_seconds=30,
    ))
    monkeypatch.setattr(
        module, "PaymentExecutionWorker", lambda **_kwargs: SimpleNamespace(run=run)
    )
    monkeypatch.setattr(module, "async_engine", SimpleNamespace(dispose=dispose))

    with pytest.raises(asyncio.CancelledError):
        await module.main()

    run.assert_awaited_once()
    dispose.assert_awaited_once()
