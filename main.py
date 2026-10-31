import logging
import sys

from dotenv import load_dotenv

from serp_mvp import pipeline

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    pipeline.run(demo="--demo" in sys.argv)
