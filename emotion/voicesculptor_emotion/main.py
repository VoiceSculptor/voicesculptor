"""Command line entry point for the emotion service."""

import argparse
from collections.abc import Sequence
import logging

import uvicorn

from voicesculptor_emotion import api
from voicesculptor_emotion import classifier as emotion_classifier
from voicesculptor_emotion import config

# 与原 server.py 一致：默认端口 50001，仅监听本机。
DEFAULT_PORT = 50001


def build_parser() -> argparse.ArgumentParser:
    """Returns the argument parser for the emotion service."""
    parser = argparse.ArgumentParser(description='声刻 情绪识别服务')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Starts the service after the model has been loaded.

    The model is created before the socket is bound, so "port is
    reachable" means "service is ready".

    Args:
      argv: Optional argument list; defaults to ``sys.argv[1:]``.
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    settings = config.Settings.from_env()
    classifier = emotion_classifier.EmotionClassifier(settings)
    classifier.load()
    uvicorn.run(
        api.create_app(classifier),
        host='127.0.0.1',
        port=args.port,
    )
