"""Allows `python -m motion_capture ...` as well as the `motion-capture` command."""

from motion_capture.cli.main import main

raise SystemExit(main())
