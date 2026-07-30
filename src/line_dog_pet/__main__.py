"""支持通过 ``python -m line_dog_pet`` 启动。"""

from .app import main


if __name__ == "__main__":
    raise SystemExit(main())
