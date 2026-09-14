import json
from pathlib import Path
from bs4 import BeautifulSoup
from tokenizer import tokenize
from collections import Counter

from bs4 import XMLParsedAsHTMLWarning, MarkupResemblesLocatorWarning
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

from tqdm import tqdm