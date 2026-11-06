#!/usr/bin/env python
"""Punto de entrada de administración de Django para la Plataforma de Bienestar Psicológico Estudiantil."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
