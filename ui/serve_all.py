"""Runs the AM2Scale host services together in one process.

Built for the container image: one container, one process, one port per service.
Which services start is controlled by SERVICES (comma-separated); each runs in
its own thread, so a slow start (discovery loads its embedding model) never
blocks the others.

    SERVICES=docs,discovery python ui/serve_all.py

Environment
    SERVICES         which services to run (default: docs,discovery)
    BIND_HOST        interface to bind (default 0.0.0.0 here, 127.0.0.1 standalone)
    DOCS_PORT        default 5190
    DISCOVERY_PORT   default 5185
    PORTAL_PORT      default 5180

Exits non-zero as soon as any service thread dies, so the container restarts
instead of sitting there half-alive.
"""
import importlib.util
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

# name -> (module path, package dir, default port)
SERVICES = {
    "docs":      ("server", "docs", 5190),
    "discovery": ("server", "discovery", 5185),
    "portal":    ("server", "portal", 5180),
}

_failed = threading.Event()
_lock = threading.Lock()


def start(name):
    module_name, package, default_port = SERVICES[name]
    port = int(os.environ.get(f"{name.upper()}_PORT") or default_port)

    # each service dir holds its own server.py, so import it under a unique name
    sys.path.insert(0, os.path.join(ROOT, package))
    try:
        with _lock:
            spec = importlib.util.spec_from_file_location(
                f"{name}_server", os.path.join(ROOT, package, f"{module_name}.py"))
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"{name}_server"] = module
            spec.loader.exec_module(module)
    except Exception as exc:                                    # noqa: BLE001
        print(f"[{name}] Import fehlgeschlagen: {exc}", flush=True)
        _failed.set()
        return

    serve = getattr(module, "serve", None)
    if serve is None:
        print(f"[{name}] hat keine serve()-Funktion", flush=True)
        _failed.set()
        return

    try:
        serve(port)
    except Exception as exc:                                    # noqa: BLE001
        print(f"[{name}] beendet: {exc}", flush=True)
        _failed.set()


def main():
    wanted = [s.strip() for s in
              (os.environ.get("SERVICES") or "docs,discovery").split(",") if s.strip()]
    unknown = [s for s in wanted if s not in SERVICES]
    if unknown:
        raise SystemExit(f"Unbekannte Dienste: {', '.join(unknown)} "
                         f"(bekannt: {', '.join(SERVICES)})")

    os.environ.setdefault("BIND_HOST", "0.0.0.0")
    print(f"Starte: {', '.join(wanted)}  (bind {os.environ['BIND_HOST']})", flush=True)

    threads = []
    for name in wanted:
        t = threading.Thread(target=start, args=(name,), name=name, daemon=True)
        t.start()
        threads.append(t)
        # discovery pulls its model in; give it a head start so the log stays readable
        if name == "discovery":
            time.sleep(0.5)

    # a dead service means the container is only half working - fail loudly
    while True:
        if _failed.is_set():
            raise SystemExit("Ein Dienst ist ausgefallen - beende den Container.")
        if not any(t.is_alive() for t in threads):
            raise SystemExit("Alle Dienste beendet.")
        time.sleep(1)


if __name__ == "__main__":
    main()
