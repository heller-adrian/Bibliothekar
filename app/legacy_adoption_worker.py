"""Start accepted adoption work independently of the HTTP response."""
from threading import Thread


def dispatch(name, target, *args, tasks=None):
    worker = Thread(target=target, args=args, name=f"adoption-{name}", daemon=True)
    worker.start()
    if tasks is not None:
        # Preserve graceful ASGI request draining after the response body. The
        # worker also starts and runs when client cancellation prevents it.
        tasks.add_task(worker.join)
    return worker
